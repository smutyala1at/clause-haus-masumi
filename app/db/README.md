# Database Setup Guide

## Prerequisites

1. PostgreSQL database (hosted on Railway or locally)
2. pgvector extension installed

## Setup Steps

### 1. Railway Setup

1. Create a new PostgreSQL database on Railway
2. Add the `pgvector` extension:
   - Go to your Railway PostgreSQL service
   - Open the PostgreSQL console
   - Run: `CREATE EXTENSION IF NOT EXISTS vector;`

### 2. Environment Variables

Add to your `.env` file:
```bash
DATABASE_URL=postgresql://user:password@host:port/dbname
```

For Railway, you can find the connection string in your PostgreSQL service settings.

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Create Initial Migration

First, create the initial migration:
```bash
alembic revision --autogenerate -m "Initial migration"
```

This will create a migration file in `alembic/versions/` based on your models.

### 5. Initialize Database

Run the initialization script (or use Alembic directly):
```bash
python -m app.db.init_db
```

Or directly with Alembic:
```bash
alembic upgrade head
```

This will:
- Run all migrations to create tables (including `bgb_embeddings`)
- Set up indexes for better query performance

### 6. Verify Setup

You can verify the setup by checking if the table exists:
```sql
SELECT * FROM bgb_embeddings LIMIT 1;
```

## Database Schema

### `bgb_embeddings` Table

Stores BGB section embeddings with metadata:

- `id`: Primary key
- `section_number`: Unique section identifier (e.g., "854", "903")
- `book`, `book_title`: Book number and title
- `division`, `division_title`: Division number and title
- `section_title`, `section_title_text`: Section title number and text
- `title`: Section title
- `content`: Section content
- `contextual_text`: Formatted text with metadata (used for embedding)
- `embedding`: Vector embedding (1536 dimensions)
- `metadata`: Additional JSON metadata
- `created_at`, `updated_at`: Timestamps

## Database Migrations

We use Alembic for database migrations. Here are common commands:

```bash
# Create a new migration (after model changes)
alembic revision --autogenerate -m "Description of changes"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# Show current migration status
alembic current

# Show migration history
alembic history
```

## Usage in Code

```python
from app.db.base import get_db
from app.db.models.bgb_embedding import BGBEmbedding
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

# In a FastAPI route
@router.get("/items")
async def get_items(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(BGBEmbedding))
    return result.scalars().all()
```

### Async Database Operations

All database operations are async. Use `await` with database queries:

```python
# Select
result = await db.execute(select(BGBEmbedding).where(BGBEmbedding.book == 3))
sections = result.scalars().all()

# Insert
new_embedding = BGBEmbedding(section_number="854", ...)
db.add(new_embedding)
await db.commit()

# Update
section = await db.get(BGBEmbedding, section_id)
section.title = "New Title"
await db.commit()

# Delete
await db.delete(section)
await db.commit()
```

