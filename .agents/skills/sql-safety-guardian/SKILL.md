---
name: sql-safety-guardian
description: Enforces read-only, parameterized, and secure SQL generation for the Text-to-SQL agent. Use this when writing database models, agent queries, or SQL executors.
---

# SQL Safety Guardian Skill

This skill enforces strict safety and security guidelines for database query generation (Text-to-SQL) in the **FinAI** codebase.

## Core Rules for SQL Execution

1. **Read-Only Context**:
   - Any database connection used by the AI chatbot MUST execute queries in a read-only transaction context.
   - The chatbot query executor MUST reject any query containing modifications: `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `TRUNCATE`, `REPLACE`, `CREATE`.

2. **SQL Injection Prevention**:
   - Never generate queries by direct string concatenation of user inputs.
   - Use SQLAlchemy/SQLModel query builders or parameterized raw SQL (using bind parameters like `:value` or `%s`).

3. **Capping & Limits**:
   - All generated SQL queries MUST specify a `LIMIT` clause (default to `LIMIT 100`) to prevent out-of-memory crashes on large historical tables.

4. **Schema Hiding**:
   - Avoid exposing internal security tables, logs, or system tables to the user-facing AI model.

## Query Construction Example

### Bad (Vulnerable)
```python
# String formatting is vulnerable to SQL injection
query = f"SELECT * FROM expenses WHERE category = '{user_input}'"
session.exec(query)
```

### Good (Secure)
```python
# Parameterized query protects against injection
query = select(Expense).where(Expense.category == user_input).limit(100)
results = session.exec(query).all()
```
