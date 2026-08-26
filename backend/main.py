from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine

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

# Test the connection
try:
    with engine.connect() as connection:
        print("Connection successful!")
except Exception as e:
    print(f"Failed to connect: {e}")