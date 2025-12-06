-- Setup script for Railway PostgreSQL with pgvector
-- Run this in your Railway PostgreSQL console

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Verify extension is installed
SELECT * FROM pg_extension WHERE extname = 'vector';

-- The tables will be created automatically by the init_db.py script
-- But you can verify with:
-- \dt

