import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Explicitly load environment variables from your .env file
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# Initialize SQLAlchemy engine for PostgreSQL with pgvector support
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()