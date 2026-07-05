import os
from typing import List, Optional
from datetime import datetime
import pandas as pd  # type: ignore
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from pydantic import BaseModel
from sqlmodel import Session, select, delete
from sqlalchemy import func
from app.db import engine, get_session
from app.models import Expense as DBExpense

router = APIRouter()

class ExpenseCreate(BaseModel):
    date: str
    description: str
    category: str
    amount: float

def get_season(date_val) -> str:
    """
    Derive the season name based on a date object's month.
    """
    month = date_val.month
    if month in [12, 1, 2]:
        return "Winter"
    elif month in [3, 4, 5]:
        return "Spring"
    elif month in [6, 7, 8]:
        return "Summer"
    else:
        return "Autumn"

def load_expenses() -> List[DBExpense]:
    """
    Load all expenses from the database for compatibility/fallback.
    """
    with Session(engine) as session:
        statement = select(DBExpense).order_by(DBExpense.date.desc())  # type: ignore
        results = session.exec(statement).all()
        return list(results)

def clean_amount(val) -> float:
    """
    Clean currency format and convert to float.
    """
    if pd.isna(val):
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)

    # String cleaning
    str_val = str(val).replace("€", "").replace("$", "").replace(",", "").strip()
    try:
        return float(str_val)
    except ValueError:
        return 0.0

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
        if any(term in col for term in ["amount", "cost", "price", "value", "spent", "charge", "eur"]):
            col_map["amount"] = columns[idx]
            break
            
    # Map Category
    for idx, col in enumerate(cols_lower):
        if any(term in col for term in ["category", "tag", "type", "group", "class"]):
            col_map["category"] = columns[idx]
            break
            
    return col_map

@router.get("/", response_model=List[DBExpense])
def get_expenses(
    category: Optional[str] = None,
    session: Session = Depends(get_session)
):
    statement = select(DBExpense)
    if category:
        statement = statement.where(func.lower(DBExpense.category) == category.lower())
    statement = statement.order_by(DBExpense.date.desc())  # type: ignore
    results = session.exec(statement).all()
    return list(results)

@router.post("/", response_model=DBExpense)
def create_expense(
    expense_in: ExpenseCreate,
    session: Session = Depends(get_session)
):
    # Validate/parse date format
    try:
        parsed_date = datetime.strptime(expense_in.date, "%Y-%m-%d").date()
    except ValueError:
        # Fallback to today's date if invalid format
        parsed_date = datetime.utcnow().date()
        
    season = get_season(parsed_date)
    
    expense = DBExpense(
        date=parsed_date,
        season=season,
        description=expense_in.description,
        category=expense_in.category or "Uncategorized",
        amount=round(expense_in.amount, 2)
    )
    session.add(expense)
    session.commit()
    session.refresh(expense)
    return expense

@router.delete("/clear")
def clear_expenses(session: Session = Depends(get_session)):
    session.exec(delete(DBExpense))
    session.commit()
    return {"message": "All expenses cleared successfully"}

@router.post("/upload")
def upload_file(
    file: UploadFile = File(...),
    session: Session = Depends(get_session)
):
    filename = file.filename or ""
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
            # Fallback mapping based on index
            cols = df.columns
            mapping["date"] = cols[0] if len(cols) > 0 else None
            mapping["description"] = cols[1] if len(cols) > 1 else None
            mapping["amount"] = cols[2] if len(cols) > 2 else None
            mapping["category"] = cols[3] if len(cols) > 3 else None
            
        if not mapping["date"] or not mapping["amount"]:
            raise HTTPException(status_code=400, detail="Could not automatically identify Date and Amount columns in the spreadsheet.")
            
        imported_count = 0
        expenses_to_insert = []
        
        # Iteratively build Expense objects
        for _, row in df.iterrows():
            # Date parsing
            raw_date = row[mapping["date"]]
            if pd.isna(raw_date):
                continue
                
            try:
                parsed_date = pd.to_datetime(raw_date).date()
            except Exception:
                try:
                    parsed_date = datetime.strptime(str(raw_date)[:10], "%Y-%m-%d").date()
                except Exception:
                    continue # Skip row if date is invalid
                    
            # Description parsing
            raw_desc = row[mapping["description"]] if mapping["description"] in df.columns else "No Description"
            description = str(raw_desc).strip() if pd.notna(raw_desc) else "No Description"
            
            # Amount parsing
            raw_amt = row[mapping["amount"]]
            amount = clean_amount(raw_amt)
            if amount <= 0:
                continue # Skip row if amount is invalid
            amount = round(amount, 2)
                
            # Category parsing
            raw_cat = row[mapping["category"]] if mapping["category"] in df.columns else "Uncategorized"
            category = str(raw_cat).strip() if pd.notna(raw_cat) else "Uncategorized"
            
            season = get_season(parsed_date)
            
            db_expense = DBExpense(
                date=parsed_date,
                season=season,
                description=description,
                category=category,
                amount=amount
            )
            expenses_to_insert.append(db_expense)
            imported_count += 1
            
        if expenses_to_insert:
            for exp in expenses_to_insert:
                session.add(exp)
            session.commit()
            
        return {
            "message": f"Successfully imported {imported_count} expenses.",
            "columns_detected": {k: str(v) for k, v in mapping.items() if v is not None}
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error parsing file: {str(e)}")

@router.get("/summary")
def get_summary(session: Session = Depends(get_session)):
    statement = select(DBExpense)
    expenses = session.exec(statement).all()
    
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
    by_category: dict[str, float] = {}
    # By Month
    by_month: dict[str, float] = {}
    
    for e in expenses:
        # Category aggregation
        cat = e.category or "Uncategorized"
        by_category[cat] = by_category.get(cat, 0.0) + e.amount
        
        # Month aggregation (YYYY-MM)
        try:
            month = e.date.strftime("%Y-%m-%d")[:7] # Get YYYY-MM
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
