from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
import urllib.parse
from dotenv import load_dotenv

app = FastAPI(title="Blueprint Compliance Checker API")

# Configure CORS middleware for your frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"status": "FastAPI backend is running successfully!"}

# Load environment variables from .env
load_dotenv()

USER = os.getenv("DB_USER", "postgres")
HOST = os.getenv("DB_HOST", "db.yuhdqnhifgyqwdxugyit.supabase.co")
PORT = os.getenv("DB_PORT", "5432")
DBNAME = os.getenv("DB_NAME", "postgres")

# Safely encode the password so special characters (like '!') don't break the connection URI
ENCODED_PASSWORD = urllib.parse.quote_plus(RAW_PASSWORD)

DATABASE_URL = f"postgresql+psycopg2://{USER}:{ENCODED_PASSWORD}@{HOST}:{PORT}/{DBNAME}?sslmode=require"
# Create the SQLAlchemy engine
engine = create_engine(DATABASE_URL)
# If using Transaction Pooler or Session Pooler, we want to ensure we disable SQLAlchemy client side pooling -
# https://docs.sqlalchemy.org/en/20/core/pooling.html#switching-pool-implementations
# engine = create_engine(DATABASE_URL, poolclass=NullPool)

# Test the connection
try:
    with engine.connect() as connection:
        print("Connection successful!")
except Exception as e:
    print(f"Failed to connect: {e}")