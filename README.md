# LotUs

This project was generated with PyArch.

## Setup

1. Copy `.env.example` to `.env` and update the database settings.
2. Configure the application and test databases.
3. Generate and apply the first migration:

```bash
uv run alembic revision --autogenerate -m "initial"
uv run alembic upgrade head
```

Run the API:

```bash
uv run uvicorn app.main:app --reload
```
