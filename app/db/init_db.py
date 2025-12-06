"""
Initialize database using Alembic migrations.
This script runs the initial migration to set up the database schema.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.core.config import settings
from alembic.config import Config
from alembic import command


def init_db():
    """
    Initialize database by running Alembic migrations.
    This will create all tables defined in models.
    """
    if not settings.DATABASE_URL:
        print("⚠️  DATABASE_URL not set. Please set it in your .env file.")
        print("   Example: DATABASE_URL=postgresql://user:pass@host:port/dbname")
        return False
    
    try:
        print("🔧 Initializing database with Alembic...")
        # Mask password in URL for display
        display_url = settings.DATABASE_URL
        if "@" in display_url:
            parts = display_url.split("@")
            if ":" in parts[0]:
                user_pass = parts[0].split(":")
                if len(user_pass) == 2:
                    display_url = f"{user_pass[0]}:****@{parts[1]}"
        print(f"   Database URL: {display_url}")
        
        # Setup Alembic
        alembic_cfg = Config("alembic.ini")
        
        # Set database URL in config
        database_url = settings.DATABASE_URL
        if database_url.startswith("postgresql://"):
            database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        alembic_cfg.set_main_option("sqlalchemy.url", database_url)
        
        # Run migrations to head
        print("   Running migrations...")
        command.upgrade(alembic_cfg, "head")
        
        print("✅ Database initialized successfully!")
        print("   Tables created via Alembic migrations:")
        print("     - bgb_embeddings")
        return True
        
    except Exception as e:
        print(f"❌ Error initializing database: {str(e)}")
        print("\n💡 Make sure:")
        print("   1. PostgreSQL is running")
        print("   2. pgvector extension is installed")
        print("   3. DATABASE_URL is correct")
        print("   4. Database user has CREATE privileges")
        print("   5. asyncpg is installed: pip install asyncpg")
        print("   6. Run 'alembic revision --autogenerate -m \"Initial migration\"' first if no migrations exist")
        return False


def create_pgvector_extension():
    """
    Create pgvector extension in the database.
    This needs to be run manually in PostgreSQL or via a migration.
    """
    print("\n📝 To enable pgvector, run this SQL in your database:")
    print("   CREATE EXTENSION IF NOT EXISTS vector;")
    print("\n   Or via psql:")
    print("   psql -d your_database -c 'CREATE EXTENSION IF NOT EXISTS vector;'")


if __name__ == "__main__":
    success = init_db()
    if success:
        create_pgvector_extension()
    sys.exit(0 if success else 1)
