import json
import uuid

import pytest

from app.agent import tools


async def test_get_schema_info_mentions_expenses_columns():
    schema = await tools.get_schema_info()
    assert "expenses" in schema
    assert "user_id" in schema
    assert "category" in schema


def test_user_id_param_sqlite_returns_hex():
    uid = uuid.uuid4()
    assert tools._user_id_param(str(uid), "sqlite") == uid.hex


def test_user_id_param_postgres_returns_hyphenated():
    uid = uuid.uuid4()
    assert tools._user_id_param(str(uid), "postgresql") == str(uid)


async def test_query_transactions_filters_by_category(seeded_expenses, user_id):
    result = json.loads(await tools.query_transactions(user_id=str(user_id), category="Groceries"))
    descriptions = {row["description"] for row in result["transactions"]}
    assert descriptions == {"Esselunga", "Conad"}


async def test_query_transactions_only_returns_requesting_users_rows(seeded_expenses, user_id):
    result = json.loads(await tools.query_transactions(user_id=str(user_id), limit=10))
    amounts = {row["amount"] for row in result["transactions"]}
    assert 999.0 not in amounts
    assert len(result["transactions"]) == 3


async def test_query_transactions_orders_by_amount_desc(seeded_expenses, user_id):
    result = json.loads(
        await tools.query_transactions(user_id=str(user_id), order_by="amount", order_direction="desc")
    )
    amounts = [row["amount"] for row in result["transactions"]]
    assert amounts == sorted(amounts, reverse=True)


async def test_query_transactions_no_match_returns_message(seeded_expenses, user_id):
    result = json.loads(await tools.query_transactions(user_id=str(user_id), description_contains="nonexistent"))
    assert result["transactions"] == []
    assert "message" in result


async def test_query_category_totals_group_by_category(seeded_expenses, user_id):
    result = json.loads(await tools.query_category_totals(user_id=str(user_id), group_by="category"))
    totals = {row["group_key"]: row["total"] for row in result["totals"]}
    assert totals == {"Groceries": 80.0, "Electricity": 80.0}


async def test_query_category_totals_group_by_season(seeded_expenses, user_id):
    result = json.loads(await tools.query_category_totals(user_id=str(user_id), group_by="season"))
    totals = {row["group_key"]: row["total"] for row in result["totals"]}
    assert totals == {"Winter": 80.0, "Summer": 80.0}


async def test_query_category_totals_respects_date_range(seeded_expenses, user_id):
    result = json.loads(
        await tools.query_category_totals(
            user_id=str(user_id), group_by="category", date_from="2025-06-01", date_to="2025-06-30"
        )
    )
    totals = {row["group_key"]: row["total"] for row in result["totals"]}
    assert totals == {"Electricity": 80.0}


async def test_query_category_totals_no_match_returns_message(seeded_expenses, other_user_id):
    result = json.loads(
        await tools.query_category_totals(user_id=str(uuid.uuid4()), group_by="category")
    )
    assert result["totals"] == []
    assert "message" in result


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM expenses WHERE user_id = 'x'",
        "UPDATE expenses SET amount = 0 WHERE user_id = 'x'",
        "DROP TABLE expenses",
        "INSERT INTO expenses VALUES (1)",
    ],
)
def test_validate_read_only_sql_rejects_mutations(sql):
    with pytest.raises(ValueError, match="forbidden keyword"):
        tools._validate_read_only_sql(sql, "someuser")


def test_validate_read_only_sql_rejects_non_select():
    with pytest.raises(ValueError, match="only SELECT queries"):
        tools._validate_read_only_sql("EXPLAIN SELECT * FROM expenses", "someuser")


def test_validate_read_only_sql_rejects_missing_user_filter():
    uid = str(uuid.uuid4())
    with pytest.raises(ValueError, match="must filter by your specific user_id"):
        tools._validate_read_only_sql("SELECT * FROM expenses", uid)


def test_validate_read_only_sql_accepts_valid_select():
    uid = str(uuid.uuid4())
    tools._validate_read_only_sql(f"SELECT * FROM expenses WHERE user_id = '{uid}'", uid)


def test_validate_read_only_sql_accepts_hex_user_filter():
    uid = uuid.uuid4()
    tools._validate_read_only_sql(f"SELECT * FROM expenses WHERE user_id = '{uid.hex}'", str(uid))


async def test_query_expenses_sql_returns_error_without_api_key(monkeypatch, seeded_expenses, user_id):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    result = json.loads(await tools.query_expenses_sql("how much did I spend total?", str(user_id)))
    assert "error" in result


async def test_query_expenses_sql_runs_generated_query(monkeypatch, seeded_expenses, user_id):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

    class FakeResponse:
        text = f"SELECT SUM(amount) as total FROM expenses WHERE user_id = '{user_id}'"

    class FakeModels:
        async def generate_content(self, model, contents):
            return FakeResponse()

    class FakeAio:
        models = FakeModels()

    class FakeClient:
        def __init__(self, api_key):
            self.aio = FakeAio()

    monkeypatch.setattr(tools.genai, "Client", FakeClient)

    result = json.loads(await tools.query_expenses_sql("how much did I spend total?", str(user_id)))
    assert result["results"][0]["total"] == 160.0


async def test_query_expenses_sql_blocks_unsafe_generated_query(monkeypatch, seeded_expenses, user_id):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

    class FakeResponse:
        text = "DELETE FROM expenses"

    class FakeModels:
        async def generate_content(self, model, contents):
            return FakeResponse()

    class FakeAio:
        models = FakeModels()

    class FakeClient:
        def __init__(self, api_key):
            self.aio = FakeAio()

    monkeypatch.setattr(tools.genai, "Client", FakeClient)

    result = json.loads(await tools.query_expenses_sql("delete everything", str(user_id)))
    assert "error" in result
