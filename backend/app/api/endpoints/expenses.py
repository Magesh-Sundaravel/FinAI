import asyncio
import os
import uuid
import json
import io
import re
from typing import List, Optional
from datetime import datetime
import pandas as pd  # type: ignore
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlmodel import select, delete
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy import func
from google import genai
from google.genai import types
from app.db import AsyncSessionLocal, get_session
from app.models import Expense as DBExpense, User
from app.auth import get_current_user

router = APIRouter()

class ExpenseCreate(BaseModel):
    date: str
    description: str
    category: str
    amount: float
    bill_image_url: Optional[str] = None

class ExpenseExtraction(BaseModel):
    description: str = Field(description="The merchant, vendor, or utility provider name (e.g. Enel, Conad, Esselunga, Fastweb, etc.).")
    category: str = Field(description="The category of spend: Choose the most appropriate from: 'Rent', 'WiFi', 'Electricity', 'Gas', 'Groceries', 'Travel & Transit', 'Gelato/Dining Out'. If none of these match, select another appropriate short category name.")
    amount: float = Field(description="The total amount of the transaction in Euros (€). If the currency is different, convert it to Euros.")
    date: str = Field(description="The transaction or invoice date in YYYY-MM-DD format.")

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

def upload_to_gcs(file_bytes: bytes, filename: str, content_type: str) -> Optional[str]:
    """
    Upload file bytes to Google Cloud Storage and return the public URL.
    Returns None if GCS_BUCKET_NAME is not set.
    """
    bucket_name = os.environ.get("GCS_BUCKET_NAME")
    if not bucket_name:
        return None
    try:
        from google.cloud import storage
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        
        # Keep GCS path structured
        unique_filename = f"uploads/{uuid.uuid4()}_{filename}"
        blob = bucket.blob(unique_filename)
        blob.upload_from_string(file_bytes, content_type=content_type)
        
        # Attempt to make public (if default IAM does not make it public)
        try:
            blob.make_public()
        except Exception:
            pass
        return blob.public_url
    except Exception as e:
        print(f"Failed to upload to GCS: {e}")
        return None

async def load_expenses() -> List[DBExpense]:
    """
    Load all expenses from the database for compatibility/fallback.
    """
    async with AsyncSessionLocal() as session:
        statement = select(DBExpense).order_by(DBExpense.date.desc())  # type: ignore
        result = await session.exec(statement)
        return list(result.all())

def clean_amount(val) -> float:
    """
    Clean currency format and convert to float.
    """
    if pd.isna(val):
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)

    # String cleaning
    str_val = str(val).replace("..", ".").replace("€", "").replace("$", "").replace(",", "").strip()
    try:
        return float(str_val)
    except ValueError:
        return 0.0

def clean_category(cat_val) -> str:
    if pd.isna(cat_val):
        return "Uncategorized"
    cat_str = str(cat_val).strip()
    
    # Remove extra interior spaces (e.g. "Apartment  Bills" -> "Apartment Bills")
    cat_str = " ".join(cat_str.split())
    cat_lower = cat_str.lower()
    
    # 1. Groceries
    if cat_lower in ('groceries', 'grocercies', 'supermarket', 'mercato', 'grocery'):
        return "Groceries"
        
    # 2. Gelato & Dining Out
    if cat_lower in ('dine out', 'dineout', 'dinner', 'treat', 'cofee', 'coffee', 'cake', 'cakes', 'outing'):
        return "Gelato/Dining Out"
        
    # 3. Rent
    if cat_lower == 'rent':
        return "Rent"
        
    # 4. Phone Bill
    if cat_lower in ('phone bill', 'phone bills', 'phonebill', 'phone', 'recharge'):
        return "Phone Bill"
        
    # 5. Apartment Bills
    if cat_lower in ('apartment bill', 'apartment bills', 'apartments bills', 'appartment bill'):
        return "Apartment Bills"
        
    # 6. Apartment Items
    if cat_lower in ('apartment items', 'apartments items', 'appartment items', 'fan'):
        return "Apartment Items"
        
    # 7. Clothing & Shoes
    if cat_lower in ('clothes', 'dress', 'shoe', 'shoes'):
        return "Clothing & Shoes"
        
    # 8. Bicycle & Cycle
    if cat_lower in ('bicycle', 'bicycle parts', 'cycle', 'cycle parts'):
        return "Bicycle/Cycle"
        
    # 9. Grooming
    if cat_lower in ('groom', 'groom up', 'grooming', 'haircut', 'facewash'):
        return "Grooming"
        
    # 10. Travel & Transit
    if cat_lower in ('train', 'transport', 'public transit', 'metro', 'bus', 'taxi', 'travel', 'flight', 'hotel'):
        return "Travel & Transit"
        
    # 12. Entertainment & Leisure
    if cat_lower in ('club', 'movie', 'party'):
        return "Entertainment & Leisure"
        
    # 13. Gifts
    if cat_lower in ('gift', 'gifts'):
        return "Gifts"
        
    # 14. Medical & Hospital
    if cat_lower in ('hospital', 'medical'):
        return "Medical/Hospital"
        
    # 15. Fees & Licenses
    if cat_lower in ('fees', 'license', 'licenses'):
        return "Fees & Licenses"
        
    # 16. Apartment Repair
    if cat_lower == 'apartment repair':
        return "Apartment Repair"
        
    # 17. General / Others
    if cat_lower in ('general', 'extra', 'others', 'shop', 'stamp', 'expeneses', 'expenses', 'bill', 'ipad', 'italian class', 'volleyball'):
        return "General/Others"
        
    return cat_str.title()

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
async def get_expenses(
    category: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    statement = select(DBExpense).where(DBExpense.user_id == current_user.id)
    if category:
        statement = statement.where(func.lower(DBExpense.category) == category.lower())
    statement = statement.order_by(DBExpense.date.desc())  # type: ignore
    result = await session.exec(statement)
    return list(result.all())

@router.post("/", response_model=DBExpense)
async def create_expense(
    expense_in: ExpenseCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
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
        amount=round(expense_in.amount, 2),
        bill_image_url=expense_in.bill_image_url,
        user_id=current_user.id
    )
    session.add(expense)
    await session.commit()
    await session.refresh(expense)
    return expense

@router.delete("/clear")
async def clear_expenses(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    await session.exec(delete(DBExpense).where(DBExpense.user_id == current_user.id))
    await session.commit()
    return {"message": "All expenses cleared successfully"}

@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    save: bool = True,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    filename = file.filename or ""
    ext = os.path.splitext(filename)[1].lower()
    
    if ext not in [".csv", ".xlsx", ".xls", ".png", ".jpg", ".jpeg", ".webp"]:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file format. Please upload a spreadsheet (.csv, .xlsx, .xls) or an image (.png, .jpg, .jpeg, .webp)."
        )
        
    try:
        # 1. Handle Image Upload & Gemini Vision OCR
        if ext in [".png", ".jpg", ".jpeg", ".webp"]:
            api_key = os.environ.get("GEMINI_API_KEY")
            if not api_key:
                raise HTTPException(
                    status_code=400,
                    detail="GEMINI_API_KEY environment variable is not set. Cannot run OCR parser."
                )
                
            # Read file bytes
            file_bytes = await file.read()
            if not file_bytes:
                raise HTTPException(status_code=400, detail="The uploaded image is empty.")

            # Upload to GCS if bucket is configured
            gcs_url = await asyncio.to_thread(
                upload_to_gcs, file_bytes, file.filename or "receipt.jpg", file.content_type or "image/jpeg"
            )
            unique_filename = ""

            # Fallback to local storage if GCS is not configured
            if not gcs_url:
                uploads_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "data", "uploads")
                os.makedirs(uploads_dir, exist_ok=True)
                unique_filename = f"{uuid.uuid4()}{ext}"
                file_path = os.path.join(uploads_dir, unique_filename)

                def _write_local_file():
                    with open(file_path, "wb") as f:
                        f.write(file_bytes)

                await asyncio.to_thread(_write_local_file)

            # Invoke google-genai Client
            client = genai.Client(api_key=api_key)

            image_part = types.Part.from_bytes(
                data=file_bytes,
                mime_type=file.content_type or f"image/{ext[1:] if ext != '.jpg' else 'jpeg'}"
            )

            prompt = """
Analyze the uploaded bill or receipt image. Extract the following information:
1. Merchant/Vendor/Utility provider name (e.g. Enel, Conad, Esselunga, Fastweb).
2. Category of spend: Choose the most appropriate category from: 'Rent', 'WiFi', 'Electricity', 'Gas', 'Groceries', 'Travel & Transit', 'Gelato/Dining Out'. If none of these match, select another appropriate short category name.
3. Total amount of the transaction in Euros (€). If the currency is different, convert it to Euros.
4. Transaction or invoice date in YYYY-MM-DD format.
"""

            response = await asyncio.to_thread(
                client.models.generate_content,
                model="gemini-2.5-flash",
                contents=[image_part, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ExpenseExtraction
                )
            )

            if not response.text:
                raise HTTPException(status_code=500, detail="Empty response received from Gemini API.")

            extracted = json.loads(response.text)

            # Parse date
            date_str = extracted.get("date")
            try:
                parsed_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except Exception:
                parsed_date = datetime.utcnow().date()

            season = get_season(parsed_date)
            description = extracted.get("description", "Unknown Merchant").strip()
            category = extracted.get("category", "Groceries").strip()
            amount = clean_amount(extracted.get("amount", 0.0))
            amount = round(amount, 2)

            db_expense = DBExpense(
                date=parsed_date,
                season=season,
                description=description,
                category=category,
                amount=amount,
                bill_image_url=gcs_url if gcs_url else f"/uploads/{unique_filename}",
                user_id=current_user.id
            )

            if save:
                session.add(db_expense)
                await session.commit()
                await session.refresh(db_expense)

            return {
                "message": "Successfully parsed and imported receipt/bill." if save else "Successfully parsed receipt/bill.",
                "type": "image",
                "expense": db_expense
            }
            
        # 2. Handle Spreadsheet Ingestion
        else:
            is_multi_sheet = False
            # Read file into DataFrame or load as ExcelFile
            if ext == ".csv":
                csv_bytes = await file.read()
                df = await asyncio.to_thread(pd.read_csv, io.BytesIO(csv_bytes))
            else:
                # Read bytes and check for multi-sheet Excel format
                file_bytes = await file.read()
                xl = await asyncio.to_thread(pd.ExcelFile, io.BytesIO(file_bytes))

                # Check for sheets matching the monthly pattern
                monthly_sheets = [s for s in xl.sheet_names if re.match(r'^[A-Za-z]{3,4}_\d{4}$', s)]

                if monthly_sheets:
                    is_multi_sheet = True
                    imported_count = 0
                    expenses_to_insert = []

                    month_map = {
                        'OCT': 10, 'NOV': 11, 'DEC': 12,
                        'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
                        'JUL': 7, 'JULY': 7, 'AUG': 8, 'SEP': 9
                    }

                    for sheet in monthly_sheets:
                        parts = sheet.split('_')
                        sheet_month = month_map[parts[0].upper()]
                        sheet_year = int(parts[1])
                        
                        sheet_df = xl.parse(sheet)
                        if sheet_df.empty:
                            continue
                            
                        # Resolve columns
                        category_col = None
                        if 'Category' in sheet_df.columns:
                            category_col = 'Category'
                        elif 'Type' in sheet_df.columns:
                            category_col = 'Type'
                            
                        if not category_col or 'Cost' not in sheet_df.columns or 'Description' not in sheet_df.columns or 'Date' not in sheet_df.columns:
                            continue
                            
                        for _, row in sheet_df.iterrows():
                            desc_val = row['Description']
                            cat_val = row[category_col]
                            cost_val = row['Cost']
                            date_val = row['Date']
                            
                            if pd.isna(desc_val) and pd.isna(cost_val) and pd.isna(date_val):
                                continue
                                
                            cat_str = str(cat_val).strip().lower() if pd.notna(cat_val) else ""
                            desc_str = str(desc_val).strip().lower() if pd.notna(desc_val) else ""
                            is_total = (
                                cat_str == 'total' or 
                                desc_str == 'total' or
                                'total' in cat_str or
                                'total' in desc_str or
                                (pd.isna(date_val) and pd.isna(desc_val) and pd.isna(cat_val) and pd.notna(cost_val))
                            )
                            if is_total:
                                continue
                                
                            day = 1
                            if isinstance(date_val, (datetime, pd.Timestamp)):
                                if date_val.month == sheet_month:
                                    day = date_val.day
                                elif date_val.day == sheet_month:
                                    day = date_val.month
                                else:
                                    day = date_val.day
                            elif isinstance(date_val, str):
                                date_str_cleaned = date_val.strip()
                                parsed_day = None
                                for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y"):
                                    try:
                                        dt = datetime.strptime(date_str_cleaned, fmt)
                                        parsed_day = dt.day
                                        break
                                    except ValueError:
                                        continue
                                if parsed_day is not None:
                                    day = parsed_day
                                else:
                                    for delim in ("/", "-", "."):
                                        if delim in date_str_cleaned:
                                            try:
                                                day = int(date_str_cleaned.split(delim)[0])
                                                break
                                            except ValueError:
                                                pass
                            elif isinstance(date_val, (int, float)):
                                day = int(date_val)
                                
                            try:
                                parsed_date = datetime(sheet_year, sheet_month, day).date()
                            except ValueError:
                                parsed_date = datetime(sheet_year, sheet_month, 1).date()
                                
                            cleaned_cat = clean_category(cat_val)
                            cleaned_amt = clean_amount(cost_val)
                            if cleaned_amt <= 0:
                                continue
                                
                            cleaned_desc = str(desc_val).strip() if pd.notna(desc_val) else "Unknown Expense"
                            
                            db_expense = DBExpense(
                                date=parsed_date,
                                season=get_season(parsed_date),
                                description=cleaned_desc,
                                category=cleaned_cat,
                                amount=cleaned_amt,
                                user_id=current_user.id
                            )
                            expenses_to_insert.append(db_expense)
                            imported_count += 1
                            
                    if expenses_to_insert:
                        for exp in expenses_to_insert:
                            session.add(exp)
                        await session.commit()

                    return {
                        "message": f"Successfully cleaned and imported {imported_count} expenses from {len(monthly_sheets)} sheets.",
                        "type": "spreadsheet",
                        "columns_detected": {"mode": "historical_multi_sheet"}
                    }
                else:
                    df = xl.parse(xl.sheet_names[0])
                    
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
                
                # Check for total/summary rows first
                desc_col = mapping["description"]
                cat_col = mapping["category"]
                desc_val = row[desc_col] if desc_col in df.columns else None
                cat_val = row[cat_col] if cat_col in df.columns else None
                cost_val = row[mapping["amount"]]
                
                cat_str = str(cat_val).strip().lower() if pd.notna(cat_val) else ""
                desc_str = str(desc_val).strip().lower() if pd.notna(desc_val) else ""
                
                is_total = (
                    cat_str == 'total' or 
                    desc_str == 'total' or
                    'total' in cat_str or
                    'total' in desc_str or
                    (pd.isna(raw_date) and pd.isna(desc_val) and pd.isna(cat_val) and pd.notna(cost_val))
                )
                if is_total:
                    continue
                    
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
                category = clean_category(raw_cat)
                
                season = get_season(parsed_date)
                
                db_expense = DBExpense(
                    date=parsed_date,
                    season=season,
                    description=description,
                    category=category,
                    amount=amount,
                    user_id=current_user.id
                )
                expenses_to_insert.append(db_expense)
                imported_count += 1
                
            if expenses_to_insert:
                for exp in expenses_to_insert:
                    session.add(exp)
                await session.commit()

            return {
                "message": f"Successfully imported {imported_count} expenses.",
                "type": "spreadsheet",
                "columns_detected": {k: str(v) for k, v in mapping.items() if v is not None}
            }
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error parsing file: {str(e)}")

@router.get("/summary")
async def get_summary(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    statement = select(DBExpense).where(DBExpense.user_id == current_user.id)
    result = await session.exec(statement)
    expenses = result.all()


    if not expenses:
        return {
            "total_spent": 0.0,
            "average_transaction": 0.0,
            "transaction_count": 0,
            "by_category": {},
            "by_month": {},
            "by_season": {
                "Winter": 0.0,
                "Spring": 0.0,
                "Summer": 0.0,
                "Autumn": 0.0
            },
        }
        
    total_spent = sum(e.amount for e in expenses)
    count = len(expenses)
    avg_tx = total_spent / count if count > 0 else 0
    
    # By Category
    by_category: dict[str, float] = {}
    # By Month
    by_month: dict[str, float] = {}
    # By Season
    by_season: dict[str, float] = {
        "Winter": 0.0,
        "Spring": 0.0,
        "Summer": 0.0,
        "Autumn": 0.0
    }
    
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
            
        # Season aggregation
        season = e.season or "Unknown"
        by_season[season] = by_season.get(season, 0.0) + e.amount
            
    # Round all values
    total_spent = round(total_spent, 2)
    avg_tx = round(avg_tx, 2)
    by_category = {k: round(v, 2) for k, v in by_category.items()}
    by_month = {k: round(v, 2) for k, v in by_month.items()}
    by_season = {k: round(v, 2) for k, v in by_season.items()}
    
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
        "by_season": by_season,
    }

@router.get("/profile")
async def get_profile(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    # Calculate stats for profile page
    statement = select(DBExpense).where(DBExpense.user_id == current_user.id)
    result = await session.exec(statement)
    expenses = result.all()


    total_spent = sum(e.amount for e in expenses)
    count = len(expenses)
    
    return {
        "email": current_user.email,
        "total_spent": round(total_spent, 2),
        "transaction_count": count,
        "created_at": current_user.created_at.strftime("%Y-%m-%d") if current_user.created_at else None
    }
