# Memora — Backend

## Setup

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

## Run

```bash
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`.
Interactive docs: `http://localhost:8000/docs`.

## Health Check

```
GET /health
```

## Alembic (migrations)

Configured and ready for future model migrations:

```bash
alembic revision --autogenerate -m "message"
alembic upgrade head
```

No models exist yet — this ticket only establishes the foundation.

## Folder Structure

```
backend/
  app/
    routers/     API route definitions
    services/    Business logic layer
    models/      SQLAlchemy ORM models
    schemas/     Pydantic schemas
    database/    Engine/session/base configuration
    ml/          Machine learning components
    core/        Settings & logging
    utils/       Shared utilities
  alembic/       Database migrations
  main.py
  requirements.txt
  .env.example
```
