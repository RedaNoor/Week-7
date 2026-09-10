"""
Script to apply database_schema.sql to PostgreSQL database.
Reads DATABASE_URL from .env and applies the schema using psycopg2.
"""
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("❌ Error: DATABASE_URL not found in .env file.")
    print("Please make sure .env exists and contains a valid DATABASE_URL.")
    sys.exit(1)

# Normalise URL for psycopg2 if it has postgresql+psycopg2:// prefix
db_url = DATABASE_URL.replace("postgresql+psycopg2://", "postgresql://")

try:
    import psycopg2
except ImportError:
    print("❌ Error: psycopg2 is not installed. Please run: pip install psycopg2-binary")
    sys.exit(1)

schema_file = os.path.join(os.path.dirname(__file__), "database_schema.sql")
if not os.path.exists(schema_file):
    print(f"❌ Error: {schema_file} not found.")
    sys.exit(1)

with open(schema_file, "r", encoding="utf-8") as f:
    sql_script = f.read()

print("Connecting to database...")
try:
    conn = psycopg2.connect(db_url)
    conn.autocommit = True
    with conn.cursor() as cur:
        print("Applying database_schema.sql...")
        cur.execute(sql_script)
        cur.execute(
            "ALTER TABLE IF EXISTS leads ADD COLUMN IF NOT EXISTS profile_data JSONB DEFAULT '{}'::jsonb;"
        )
    conn.close()
    print("✅ Database schema applied successfully!")
except Exception as e:
    print(f"❌ Failed to apply database schema: {e}")
    sys.exit(1)
