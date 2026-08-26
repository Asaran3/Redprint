import os
import pymupdf
from openai import OpenAI
from dotenv import load_dotenv
from database import engine
from sqlalchemy import text

# Load environment variables from .env file
load_dotenv()

# Initialize OpenAI client for embedding generation
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def get_embedding(text_content: str):
    """Generates vector embeddings for a given text chunk using OpenAI's embedding model."""
    response = client.embeddings.create(
        input=[text_content],
        model="text-embedding-3-small"
    )
    return response.data[0].embedding

def ingest_pdf_code(file_path: str, city_name: str, code_section: str):
    """Parses a local municipal code PDF, chunks the text, and stores vectors in Supabase."""
    if not os.path.exists(file_path):
        print(f"Error: File '{file_path}' not found.")
        return

    doc = pymupdf.open(file_path)
    full_text = ""
    
    # Extract text from all pages of the PDF document[cite: 1]
    for page_num, page in enumerate(doc):
        full_text += page.get_text()
        
    # Keep embedding requests below OpenAI's 8,192-token input limit.
    chunks = []
    for paragraph in full_text.split("\n\n"):
        paragraph = paragraph.strip()
        if len(paragraph) <= 50:
            continue
        chunks.extend(
            paragraph[index:index + 12000]
            for index in range(0, len(paragraph), 12000)
        )
    
    print(f"Extracted {len(chunks)} chunks from {file_path}. Uploading to Supabase...")
    
    # Connect to your Supabase PostgreSQL database and insert chunks with their vectors[cite: 1]
    with engine.connect() as connection:
        for chunk in chunks:
            embedding = get_embedding(chunk)
            
            connection.execute(
                text("""
                    INSERT INTO municipal_codes (city_name, code_section, chunk_text, embedding)
                    VALUES (:city, :section, :text, :embedding)
                """),
                {
                    "city": city_name,
                    "section": code_section,
                    "text": chunk,
                    "embedding": str(embedding)
                }
            )
        connection.commit()
        
    print("Ingestion complete! Code chunks successfully stored in Supabase vector database.")

if __name__ == "__main__":
    # Test execution: Place a sample building code PDF in your /backend folder
    # Example: ingest_pdf_code("sample_building_code.pdf", "San Francisco", "Chapter 10 - Means of Egress")
    pass