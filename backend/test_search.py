import os
from dotenv import load_dotenv
from openai import OpenAI
from database import engine
from sqlalchemy import text

# Load environment variables from .env file
load_dotenv()

# Initialize OpenAI client for generating query embeddings
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def search_municipal_codes(query_text: str, top_k: int = 3):
    """Embeds a search query and queries Supabase pgvector using cosine distance."""
    print(f"Generating embedding for query: '{query_text}'...")
    
    # 1. Convert the natural language question into a vector embedding
    response = client.embeddings.create(
        input=[query_text],
        model="text-embedding-3-small"
    )
    query_embedding = response.data[0].embedding
    
    print("Searching Supabase pgvector database...")
    
    # 2. Query Supabase using pgvector's cosine distance operator (<=>)
    with engine.connect() as connection:
        result = connection.execute(
            text("""
                SELECT city_name, code_section, chunk_text, 
                       (embedding <=> :query_emb) AS distance
                FROM municipal_codes
                ORDER BY distance ASC
                LIMIT :limit
            """),
            {
                "query_emb": str(query_embedding),
                "limit": top_k
            }
        )
        
        rows = result.fetchall()
        
        if not rows:
            print("No matching code chunks found in the database.")
            return

        print(f"\nTop {len(rows)} Relevant Building Code Results:")
        print("=" * 60)
        for i, row in enumerate(rows, 1):
            city, section, text_chunk, distance = row
            # Convert cosine distance to a similarity score (higher is more similar)
            similarity_score = 1 - distance 
            
            print(f"Result {i}:")
            print(f"  City/Jurisdiction: {city}")
            print(f"  Code Section: {section}")
            print(f"  Match Similarity: {similarity_score:.4f}")
            print(f"  Text Snippet: {text_chunk[:250]}...")
            print("=" * 60)

if __name__ == "__main__":
    # Test query targeting your ingested California Energy Code document
    test_query = "What are the rules and definitions for exterior walls?"
    search_municipal_codes(test_query)