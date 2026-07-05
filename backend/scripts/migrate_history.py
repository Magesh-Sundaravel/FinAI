#!/usr/bin/env python3
import sys
import os
import argparse
from datetime import datetime
import pandas as pd  # type: ignore

# Add the parent directory (backend/) to the python path to allow importing app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import engine
from app.models import Expense
from sqlmodel import Session


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


def detect_columns(columns):
    """
    Identify columns representing Date, Description, Amount, and Category.
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
        if any(
            term in col
            for term in [
                "desc",
                "payee",
                "title",
                "item",
                "name",
                "transaction",
                "detail",
            ]
        ):
            col_map["description"] = columns[idx]
            break
    if col_map["description"] is None and len(columns) > 1:
        # Fallback to first non-date column
        for idx, col in enumerate(columns):
            if col != col_map["date"]:
                col_map["description"] = col
                break

    # Map Amount
    for idx, col in enumerate(cols_lower):
        if any(
            term in col
            for term in ["amount", "cost", "price", "value", "spent", "charge", "eur"]
        ):
            col_map["amount"] = columns[idx]
            break

    # Map Category
    for idx, col in enumerate(cols_lower):
        if any(term in col for term in ["category", "tag", "type", "group", "class"]):
            col_map["category"] = columns[idx]
            break

    return col_map


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


def main():
    parser = argparse.ArgumentParser(
        description="Migrate historical expense spreadsheet files into the database."
    )
    parser.add_argument(
        "file_path", help="Path to the Excel (.xlsx, .xls) or CSV (.csv) file."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse the spreadsheet and output summary analytics without saving to the database.",
    )
    parser.add_argument(
        "--default-category",
        default="Groceries",
        help="Default category to assign if missing in spreadsheet.",
    )

    args = parser.parse_args()
    file_path = args.file_path

    if not os.path.exists(file_path):
        print(f"❌ Error: File not found at '{file_path}'")
        sys.exit(1)

    ext = os.path.splitext(file_path)[1].lower()
    if ext not in [".csv", ".xlsx", ".xls"]:
        print("❌ Error: Supported formats are CSV, XLS, and XLSX only.")
        sys.exit(1)

    print(f"📖 Reading spreadsheet: {file_path}...")
    try:
        if ext == ".csv":
            df = pd.read_csv(file_path)
        else:
            df = pd.read_excel(file_path)
    except Exception as e:
        print(f"❌ Error loading file: {str(e)}")
        sys.exit(1)

    if df.empty:
        print("❌ Error: The spreadsheet file is empty.")
        sys.exit(1)

    print(f"📋 Found {len(df)} rows in spreadsheet. Scanning columns...")
    mapping = detect_columns(df.columns)

    # Enforce minimum mapping requirements
    if not mapping["date"] or not mapping["amount"]:
        print("⚠️ Warning: Auto-detection failed to find Date or Amount headers.")
        print(f"Available headers: {list(df.columns)}")
        # Simple manual fallback mapping
        cols = df.columns
        mapping["date"] = cols[0] if len(cols) > 0 else None
        mapping["description"] = cols[1] if len(cols) > 1 else None
        mapping["amount"] = cols[2] if len(cols) > 2 else None
        mapping["category"] = cols[3] if len(cols) > 3 else None
        print(f"Falling back to basic index mapping: {mapping}")

    if not mapping["date"] or not mapping["amount"]:
        print("❌ Error: Could not locate columns matching Date and Amount.")
        sys.exit(1)

    print("\n🔍 Column Ingestion Mapping:")
    for k, v in mapping.items():
        print(f"  • {k.capitalize()} ➔ {v}")

    processed_count = 0
    skipped_count = 0
    total_spend = 0.0
    category_summary = {}
    season_summary = {}

    expenses_to_insert = []

    for idx, row in df.iterrows():
        # Date parsing
        raw_date = row[mapping["date"]]
        if pd.isna(raw_date):
            skipped_count += 1
            continue

        try:
            parsed_date = pd.to_datetime(raw_date).date()
        except Exception:
            try:
                # Try string parsing
                parsed_date = datetime.strptime(str(raw_date)[:10], "%Y-%m-%d").date()
            except Exception:
                skipped_count += 1
                continue

        # Amount parsing
        raw_amount = row[mapping["amount"]]
        amount = clean_amount(raw_amount)
        if amount <= 0:
            skipped_count += 1
            continue

        # Description parsing
        desc_col = mapping["description"]
        desc = (
            str(row[desc_col]).strip()
            if desc_col in df.columns and pd.notna(row[desc_col])
            else "Unknown Merchant"
        )

        # Category parsing
        cat_col = mapping["category"]
        category = (
            str(row[cat_col]).strip()
            if cat_col in df.columns and pd.notna(row[cat_col])
            else args.default_category
        )

        # Calculate season
        season = get_season(parsed_date)

        expense = Expense(
            date=parsed_date,
            season=season,
            description=desc,
            category=category,
            amount=amount,
        )

        expenses_to_insert.append(expense)

        # In-memory stats accumulation
        processed_count += 1
        total_spend += amount
        category_summary[category] = category_summary.get(category, 0.0) + amount
        season_summary[season] = season_summary.get(season, 0.0) + amount

    print("\n📈 Migration Parsing Summary:")
    print(f"  • Successfully Parsed: {processed_count} rows")
    print(f"  • Skipped (Empty/Invalid): {skipped_count} rows")
    print(f"  • Total Calculated Spend: €{total_spend:,.2f}")

    print("\n❄️ Spending by Season:")
    for season, amt in season_summary.items():
        print(f"  • {season}: €{amt:,.2f} ({(amt / total_spend) * 100:.1f}%)")

    print("\n📂 Spending by Category (Top 5):")
    sorted_cats = sorted(category_summary.items(), key=lambda x: x[1], reverse=True)[:5]
    for cat, amt in sorted_cats:
        print(f"  • {cat}: €{amt:,.2f} ({(amt / total_spend) * 100:.1f}%)")

    if args.dry_run:
        print("\n🛡️ Dry-run mode active. No changes written to database.")
    else:
        if processed_count == 0:
            print("\n⚠️ No valid records found to save.")
            sys.exit(0)

        print(f"\n💾 Writing {processed_count} records to database...")
        try:
            with Session(engine) as session:
                for exp in expenses_to_insert:
                    session.add(exp)
                session.commit()
            print("🚀 Successfully migrated historical database!")
        except Exception as e:
            print(f"❌ Database error: {str(e)}")
            sys.exit(1)


if __name__ == "__main__":
    main()
