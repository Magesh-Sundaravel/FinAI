import os
import sys
import uuid
import re
from datetime import datetime, date
import pandas as pd
from sqlmodel import SQLModel, Session, select

# Add parent directory of scripts to Python path so we can import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import DATABASE_URL, engine
from app.models import Expense

EXCEL_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "historical_expenses.xlsx")
CLEANED_CSV_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "cleaned_historical_expenses.csv")

MONTH_MAP = {
    'OCT': 10, 'NOV': 11, 'DEC': 12,
    'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
    'JUL': 7, 'AUG': 8, 'SEP': 9
}

def get_season(date_val) -> str:
    month = date_val.month
    if month in (12, 1, 2):
        return "Winter"
    elif month in (3, 4, 5):
        return "Spring"
    elif month in (6, 7, 8):
        return "Summer"
    else:
        return "Autumn"

def parse_sheet_date(val, sheet_name) -> date:
    # Extract month and year from sheet name (e.g. OCT_2020)
    parts = sheet_name.split('_')
    sheet_month = MONTH_MAP[parts[0].upper()]
    sheet_year = int(parts[1])
    
    if pd.isna(val):
        return date(sheet_year, sheet_month, 1)
        
    day = 1
    if isinstance(val, (datetime, pd.Timestamp)):
        # If parsed month matches sheet, take parsed day
        if val.month == sheet_month:
            day = val.day
        # If parsed day matches sheet, take parsed month (due to format swap)
        elif val.day == sheet_month:
            day = val.month
        else:
            day = val.day
    elif isinstance(val, str):
        val = val.strip()
        parsed_day = None
        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y"):
            try:
                dt = datetime.strptime(val, fmt)
                parsed_day = dt.day
                break
            except ValueError:
                continue
        if parsed_day is not None:
            day = parsed_day
        else:
            # Fallback string parsing (extract leading integer digits)
            for delim in ("/", "-", "."):
                if delim in val:
                    try:
                        day = int(val.split(delim)[0])
                        break
                    except ValueError:
                        pass
    elif isinstance(val, (int, float)):
        day = int(val)
        
    # Validation boundary check for days in month
    try:
        return date(sheet_year, sheet_month, day)
    except ValueError:
        # Fallback if day is invalid (e.g. 31st of November)
        return date(sheet_year, sheet_month, 1)

def clean_amount(val) -> float:
    if isinstance(val, (int, float)):
        return float(val)
    if not val:
        return 0.0
    val_str = str(val).strip()
    # Correct double decimal typos like '8..31'
    val_str = val_str.replace('..', '.')
    val_str = val_str.replace('€', '').replace('$', '').replace('£', '')
    val_str = val_str.replace(',', '').strip()
    try:
        return round(float(val_str), 2)
    except ValueError:
        return 0.0

def clean_category(cat_val) -> str:
    if pd.isna(cat_val):
        return "Uncategorized"
    cat_str = str(cat_val).strip().lower()
    
    # Standardize names matching UI Categories
    if cat_str in ('groceries', 'supermarket', 'mercato'):
        return "Groceries"
    elif cat_str in ('dine out', 'dineout', 'restaurant', 'food', 'gelato'):
        return "Gelato/Dining Out"
    elif cat_str in ('transport', 'public transit', 'metro', 'train', 'bus', 'taxi'):
        return "Public Transit"
    elif cat_str in ('wifi', 'internet', 'fastweb'):
        return "WiFi"
    elif cat_str in ('electricity', 'enel', 'power'):
        return "Electricity"
    elif cat_str in ('gas', 'heating'):
        return "Gas"
    elif cat_str in ('rent', 'housing'):
        return "Rent"
    elif cat_str in ('travel', 'flight', 'hotel'):
        return "Travel"
    
    # Default to title case for other categories
    return str(cat_val).strip().title()

def clean_description(desc_val) -> str:
    if pd.isna(desc_val):
        return "Unknown Expense"
    return str(desc_val).strip()

def process_excel():
    print(f"Opening Excel workbook: {EXCEL_PATH}")
    xl = pd.ExcelFile(EXCEL_PATH)
    
    cleaned_rows = []
    skipped_totals = 0
    skipped_empty = 0
    
    for sheet in xl.sheet_names:
        # Check sheet name matches expected pattern (e.g. OCT_2020)
        if not re.match(r'^[A-Za-z]{3}_\d{4}$', sheet):
            print(f"Skipping sheet with invalid format name: {sheet}")
            continue
            
        df = xl.parse(sheet)
        
        # Resolve category column name
        category_col = None
        if 'Category' in df.columns:
            category_col = 'Category'
        elif 'Type' in df.columns:
            category_col = 'Type'
            
        if not category_col or 'Cost' not in df.columns or 'Description' not in df.columns or 'Date' not in df.columns:
            print(f"Skipping sheet '{sheet}' due to missing standard columns (found {df.columns.tolist()})")
            continue
            
        print(f"Processing sheet '{sheet}'...")
        
        for idx, row in df.iterrows():
            desc_val = row['Description']
            cat_val = row[category_col]
            cost_val = row['Cost']
            date_val = row['Date']
            
            # Skip empty rows
            if pd.isna(desc_val) and pd.isna(cost_val) and pd.isna(date_val):
                skipped_empty += 1
                continue
                
            # Skip summary/Total rows
            cat_str = str(cat_val).strip().lower() if pd.notna(cat_val) else ""
            desc_str = str(desc_val).strip().lower() if pd.notna(desc_val) else ""
            if cat_str == 'total' or desc_str == 'total':
                skipped_totals += 1
                continue
                
            # Parse & Clean
            expense_date = parse_sheet_date(date_val, sheet)
            expense_season = get_season(expense_date)
            expense_desc = clean_description(desc_val)
            expense_cat = clean_category(cat_val)
            expense_amount = clean_amount(cost_val)
            
            cleaned_rows.append({
                "date": expense_date.strftime("%Y-%m-%d"),
                "season": expense_season,
                "description": expense_desc,
                "category": expense_cat,
                "amount": expense_amount
            })
            
    print(f"\nCleaning finished! Total clean entries: {len(cleaned_rows)}")
    print(f"Skipped summary rows: {skipped_totals} | Skipped empty rows: {skipped_empty}")
    
    # Save cleaned data to CSV
    cleaned_df = pd.DataFrame(cleaned_rows)
    os.makedirs(os.path.dirname(CLEANED_CSV_PATH), exist_ok=True)
    cleaned_df.to_csv(CLEANED_CSV_PATH, index=False)
    print(f"Cleaned dataset saved locally to: {CLEANED_CSV_PATH}")
    
    return cleaned_rows

def import_to_db(records):
    print(f"\nConnecting to database at: {DATABASE_URL}")
    
    # Ensure tables exist
    SQLModel.metadata.create_all(engine)
    
    with Session(engine) as session:
        # Check if we have existing records
        existing_count = session.exec(select(Expense)).first()
        if existing_count is not None:
            print("⚠️ Database already contains records.")
            
        print(f"Importing {len(records)} records...")
        
        batch = []
        batch_size = 500
        for i, rec in enumerate(records):
            expense = Expense(
                id=uuid.uuid4(),
                date=datetime.strptime(rec["date"], "%Y-%m-%d").date(),
                season=rec["season"],
                description=rec["description"],
                category=rec["category"],
                amount=rec["amount"],
                bill_image_url=None
            )
            batch.append(expense)
            
            if len(batch) >= batch_size:
                session.add_all(batch)
                session.commit()
                batch = []
                print(f"Inserted {i + 1}/{len(records)} records...")
                
        if batch:
            session.add_all(batch)
            session.commit()
            print(f"Inserted {len(records)}/{len(records)} records successfully.")
            
    print("🎉 Database migration completed!")

if __name__ == "__main__":
    if not os.path.exists(EXCEL_PATH):
        print(f"❌ Error: Excel file not found at {EXCEL_PATH}")
        print("Please copy your spreadsheet to that path and run again.")
        sys.exit(1)
        
    records = process_excel()
    if records:
        import_to_db(records)
