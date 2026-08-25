from sqlalchemy import text
from database import engine

def test_connection():
    try:
        # Attempt to open a connection and run a simple query
        with engine.connect() as connection:
            result = connection.execute(text("SELECT version();"))
            db_version = result.fetchone()
            print("Successfully connected to Supabase PostgreSQL!")
            print(f"Database Version: {db_version[0]}")
    except Exception as e:
        print("Database connection failed!")
        print(f"Error: {e}")

if __name__ == "__main__":
    test_connection()