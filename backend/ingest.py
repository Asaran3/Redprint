import os
from dotenv import load_dotenv
from openai import OpenAI
from database import engine
from sqlalchemy import text
from enterprise_parser import parse_pdf_enterprise

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def get_embedding(text_content: str):
    """Generates vector embeddings for a text chunk using OpenAI."""
    response = client.embeddings.create(
        input=[text_content],
        model="text-embedding-3-small"
    )
    return response.data[0].embedding

def run_smart_ingestion(pdf_path: str, city_name: str):
    """Orchestrates ingestion using the 3 advanced enterprise parsing implementations."""
    print(f"Starting smart enterprise ingestion for: {pdf_path} ({city_name})")
    
    parsed_chunks = parse_pdf_enterprise(pdf_path, city_name)
    
    if not parsed_chunks:
        print("No valid chunks were extracted from the document.")
        return

    print(f"Embedding and uploading {len(parsed_chunks)} substantive chunks to Supabase pgvector...")
    
    with engine.connect() as connection:
        for item in parsed_chunks:
            chunk_text = item["content"]
            section_label = item["section"]
            
            embedding = get_embedding(chunk_text)
            
            connection.execute(
                text("""
                    INSERT INTO municipal_codes (city_name, code_section, chunk_text, embedding)
                    VALUES (:city, :section, :text, :embedding)
                """),
                {
                    "city": city_name,
                    "section": section_label,
                    "text": chunk_text,
                    "embedding": str(embedding)
                }
            )
        connection.commit()
        
    print("Ingestion complete! Clean substantive code chunks successfully stored in pgvector.")

if __name__ == "__main__":
    run_smart_ingestion("SampleCodeDoc.pdf", city_name="San Francisco")