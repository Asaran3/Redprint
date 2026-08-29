import json

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from database import engine
from schemas import ComplianceReport
from services.blueprint import extract_blueprint
from services.geocoder import resolve_jurisdiction
from services.rag_service import generate_full_report

app = FastAPI(title="Redprint Compliance API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"status": "ok", "service": "redprint"}


@app.post("/api/analyze", response_model=ComplianceReport)
async def analyze_blueprint(
    address: str = Form(...),
    blueprint: UploadFile = File(...),
):
    cleaned_address = address.strip()
    if not cleaned_address:
        raise HTTPException(status_code=400, detail="Address is required.")

    filename = blueprint.filename or "blueprint.pdf"
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Upload a PDF blueprint.")

    pdf_bytes = await blueprint.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="Blueprint file is empty.")
    if len(pdf_bytes) > 25 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Blueprint exceeds 25 MB.")

    location = resolve_jurisdiction(cleaned_address)
    if location.get("error"):
        raise HTTPException(status_code=422, detail=location["error"])

    try:
        extracted = extract_blueprint(pdf_bytes)
        return generate_full_report(
            filename=filename,
            jurisdiction=location,
            blueprint=extracted,
        )
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=502,
            detail="Compliance model returned invalid JSON.",
        ) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# Keep import side-effect connection check used in local setup
try:
    with engine.connect() as connection:
        print("Connection successful!")
except Exception as e:
    print(f"Failed to connect: {e}")
