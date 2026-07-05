import os
import json
import uuid
from typing import List, Optional
from datetime import datetime
import pandas as pd
from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter()

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
DB_FILE = os.path.join(DB_DIR, "expenses.json")

# Ensure database directory exists
os.makedirs(DB_DIR, exist_ok=True)

class Expense(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    date: str
    description: str
    category: str
    amount: float

class ExpenseCreate(BaseModel):
    date: str
    description: str
    category: str
    amount: float

def load_expenses() -> List[Expense]:
    if not os.path.exists(DB_FILE):
        return []
    try:
        with open(DB_FILE, "r") as f:
            data = json.load(f)
            return [Expense(**item) for item in data]
    except Exception:
        return []

def save_expenses(expenses: List[Expense]):
    with open(DB_FILE, "w") as f:
        json.dump([e.model_dump() for e in expenses], f, indent=2)

def detect_columns(columns):
    """
    Attempt to map input spreadsheet columns to Date, Description, Amount, and Category.
    """
    col_map = {"date": None, "description": None, "amount": None, "category": None}
    
    cols_lower = [str(c).lower().strip() for c in columns]
    
    # Map Date
    for idx, col in enumerate(cols_lower):
        if any(term in col for term in ["date", "time", "timestamp"]):
            col_map["date"] = columns[idx]
            break
            
    # Map Description
    for idx, col in enumerate(cols_lower):
        if any(term in col for term in ["desc", "payee", "title", "item", "name", "transaction", "detail"]):
            col_map["description"] = columns[idx]
            break
    if col_map["description"] is None:
        # Fallback to any string col
        for idx, col in enumerate(columns):
            if col != col_map["date"]:
                col_map["description"] = col
                break

    # Map Amount
    for idx, col in enumerate(cols_lower):
        if any(term in col for term in ["amount", "cost", "price", "value", "spent", "charge"]):
            col_map["amount"] = columns[idx]
            break
            
    # Map Category
    for idx, col in enumerate(cols_lower):
        if any(term in col for term in ["category", "tag", "type", "group", "class"]):
            col_map["category"] = columns[idx]
            break
            
    return col_map

@router.get("/", response_model=List[Expense])
def get_expenses(category: Optional[str] = None):
    expenses = load_expenses()
    if category:
        expenses = [e for e in expenses if e.category.lower() == category.lower()]
    # Sort by date descending
    try:
        expenses.sort(key=lambda x: x.date, reverse=True)
    except Exception:
        pass
    return expenses

@router.post("/", response_model=Expense)
def create_expense(expense_in: ExpenseCreate):
    expenses = load_expenses()
    
    # Simple validation of date format
    try:
        datetime.strptime(expense_in.date, "%Y-%m-%d")
    except ValueError:
        # Fallback to current date or try parsing
        pass
        
    expense = Expense(
        date=expense_in.date,
        description=expense_in.description,
        category=expense_in.category or "Uncategorized",
        amount=expense_in.amount
    )
    expenses.append(expense)
    save_expenses(expenses)
    return expense

@router.delete("/clear")
def clear_expenses():
    save_expenses([])
    return {"message": "All expenses cleared successfully"}

@router.post("/upload")
def upload_file(file: UploadFile = File(...)):
    filename = file.filename
    ext = os.path.splitext(filename)[1].lower()
    
    if ext not in [".csv", ".xlsx", ".xls"]:
        raise HTTPException(status_code=400, detail="Only CSV or Excel files are supported.")
        
    try:
        # Read file into DataFrame
        if ext == ".csv":
            df = pd.read_csv(file.file)
        else:
            df = pd.read_excel(file.file)
            
        if df.empty:
            raise HTTPException(status_code=400, detail="The uploaded file is empty.")
            
        # Detect mapping
        mapping = detect_columns(df.columns)
        
        # We need at least Date and Amount
        if not mapping["date"] or not mapping["amount"]:
            # Fallback to first column as date, second as description, third as amount
            cols = df.columns
            mapping["date"] = cols[0] if len(cols) > 0 else None
            mapping["description"] = cols[1] if len(cols) > 1 else None
            mapping["amount"] = cols[2] if len(cols) > 2 else None
            mapping["category"] = cols[3] if len(cols) > 3 else None
            
        if not mapping["date"] or not mapping["amount"]:
            raise HTTPException(status_code=400, detail="Could not automatically identify Date and Amount columns in the spreadsheet.")
            
        imported_count = 0
        expenses = load_expenses()
        
        # Iteratively build Expense objects
        for _, row in df.iterrows():
            # Date parsing
            raw_date = row[mapping["date"]]
            parsed_date = "2026-01-01"  # fallback
            if pd.notna(raw_date):
                try:
                    # Let pandas handle parsing date strings or timestamps
                    parsed_date = pd.to_datetime(raw_date).strftime("%Y-%m-%d")
                except Exception:
                    parsed_date = str(raw_date)[:10]
                    
            # Description parsing
            raw_desc = row[mapping["description"]] if mapping["description"] in df.columns else "No Description"
            description = str(raw_desc) if pd.notna(raw_desc) else "No Description"
            
            # Amount parsing
            raw_amt = row[mapping["amount"]]
            try:
                # Clean up currency symbols or string values if any
                if isinstance(raw_amt, str):
                    raw_amt = raw_amt.replace("$", "").replace(",", "").strip()
                amount = float(raw_amt)
            except Exception:
                continue # Skip row if amount is invalid
                
            # Category parsing
            raw_cat = row[mapping["category"]] if mapping["category"] in df.columns else "Uncategorized"
            category = str(raw_cat) if pd.notna(raw_cat) else "Uncategorized"
            
            expense = Expense(
                date=parsed_date,
                description=description,
                category=category,
                amount=amount
            )
            expenses.append(expense)
            imported_count += 1
            
        save_expenses(expenses)
        
        return {
            "message": f"Successfully imported {imported_count} expenses.",
            "columns_detected": {k: str(v) for k, v in mapping.items() if v is not None}
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error parsing file: {str(e)}")

@router.get("/summary")
def get_summary():
    expenses = load_expenses()
    if not expenses:
        return {
            "total_spent": 0.0,
            "average_transaction": 0.0,
            "transaction_count": 0,
            "by_category": {},
            "by_month": {},
        }
        
    total_spent = sum(e.amount for e in expenses)
    count = len(expenses)
    avg_tx = total_spent / count if count > 0 else 0
    
    # By Category
    by_category = {}
    # By Month
    by_month = {}
    
    for e in expenses:
        # Category aggregation
        cat = e.category or "Uncategorized"
        by_category[cat] = by_category.get(cat, 0.0) + e.amount
        
        # Month aggregation (YYYY-MM)
        try:
            month = e.date[:7] # Get YYYY-MM
            # Validate format is YYYY-MM
            if len(month) == 7 and month[4] == "-":
                by_month[month] = by_month.get(month, 0.0) + e.amount
            else:
                by_month["Unknown"] = by_month.get("Unknown", 0.0) + e.amount
        except Exception:
            by_month["Unknown"] = by_month.get("Unknown", 0.0) + e.amount
            
    # Round all values
    total_spent = round(total_spent, 2)
    avg_tx = round(avg_tx, 2)
    by_category = {k: round(v, 2) for k, v in by_category.items()}
    by_month = {k: round(v, 2) for k, v in by_month.items()}
    
    # Sort months chronologically
    sorted_months = dict(sorted(by_month.items()))
    
    # Sort categories by spending descending
    sorted_categories = dict(sorted(by_category.items(), key=lambda item: item[1], reverse=True))
    
    return {
        "total_spent": total_spent,
        "average_transaction": avg_tx,
        "transaction_count": count,
        "by_category": sorted_categories,
        "by_month": sorted_months,
    }
