import argparse
import asyncio
import csv
import datetime as dt
import os
import sys
from pathlib import Path

from sqlmodel import delete, func, select

sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.db import AsyncSessionLocal, init_db
from app.models import Expense, User

DEFAULT_CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "cleaned_historical_expenses.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed the local development database from cleaned_historical_expenses.csv."
    )
    parser.add_argument(
        "--email",
        default=None,
        help="User email to own the imported expenses. Defaults to DEV_USER_EMAIL when set.",
    )
    parser.add_argument(
        "--csv",
        dest="csv_path",
        default=str(DEFAULT_CSV_PATH),
        help="Path to the cleaned CSV file.",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete existing expenses for the user before importing.",
    )
    return parser.parse_args()


def resolve_seed_email(email_arg: str | None) -> str:
    if email_arg and email_arg.strip():
        return email_arg.strip()

    env_email = os.environ.get("DEV_USER_EMAIL", "").strip()
    if env_email:
        return env_email

    raise SystemExit(
        "No seed email provided. Pass --email or set DEV_USER_EMAIL so local auth and seeded data use the same user."
    )


def load_records(csv_path: Path) -> list[dict[str, object]]:
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required_columns = {"date", "season", "description", "category", "amount"}
        missing = required_columns - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"CSV file is missing required columns: {sorted(missing)}")

        records: list[dict[str, object]] = []
        for row in reader:
            if not row["date"] or not row["description"]:
                continue

            records.append(
                {
                    "date": dt.date.fromisoformat(row["date"]),
                    "season": (row["season"] or "").strip(),
                    "description": (row["description"] or "").strip(),
                    "category": (row["category"] or "Uncategorized").strip(),
                    "amount": round(float(row["amount"] or 0), 2),
                }
            )
    return records


async def get_or_create_user(email: str) -> User:
    async with AsyncSessionLocal() as session:
        result = await session.exec(select(User).where(User.email == email))
        user = result.first()
        if user:
            return user

        user = User(email=email)
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


async def seed_local_data(email: str, csv_path: Path, reset: bool) -> None:
    await init_db()
    records = load_records(csv_path)
    user = await get_or_create_user(email)

    async with AsyncSessionLocal() as session:
        count_stmt = select(func.count()).select_from(Expense).where(Expense.user_id == user.id)
        existing_count = (await session.exec(count_stmt)).one()

        if existing_count and not reset:
            print(
                f"Skipped import: {existing_count} expenses already exist for {email}. "
                "Pass --reset to replace them."
            )
            return

        if existing_count and reset:
            await session.exec(delete(Expense).where(Expense.user_id == user.id))
            await session.commit()

        expenses = [
            Expense(
                date=record["date"],
                season=str(record["season"]),
                description=str(record["description"]),
                category=str(record["category"]),
                amount=float(record["amount"]),
                user_id=user.id,
            )
            for record in records
        ]
        session.add_all(expenses)
        await session.commit()

    print(f"Imported {len(records)} expenses for {email} from {csv_path}.")


def main() -> None:
    args = parse_args()
    asyncio.run(seed_local_data(resolve_seed_email(args.email), Path(args.csv_path), args.reset))


if __name__ == "__main__":
    main()
