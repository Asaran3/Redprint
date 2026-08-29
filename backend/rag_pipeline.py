import os
from dotenv import load_dotenv
from openai import OpenAI
import anthropic
from database import engine
from sqlalchemy import text

load_dotenv()

openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
claude_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

def retrieve_code_chunks(query_text: str, top_k: int = 3):
    """Embeds user query and fetches relevant enterprise semantic chunks from Supabase pgvector."""
    response = openai_client.embeddings.create(
        input=[query_text],
        model="text-embedding-3-small"
    )
    query_embedding = response.data[0].embedding
    
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
        return result.fetchall()

def evaluate_compliance(query_text: str):
    """Performs RAG compliance checks using the newly ingested enterprise semantic chunks."""
    print(f"Searching enterprise knowledge base for: '{query_text}'...")
    chunks = retrieve_code_chunks(query_text, top_k=3)
    
    if not chunks:
        return "No relevant building codes found in the database."
    
    context_str = ""
    for i, row in enumerate(chunks, 1):
        city, section, text_chunk, distance = row
        similarity = 1 - distance
        context_str += f"\n--- Source [{i}] (Similarity Score: {similarity:.4f}) ---\n"
        context_str += f"Jurisdiction: {city} | Section/Segment: {section}\n"
        context_str += f"Content: {text_chunk}\n"
    
    system_prompt = (
        "You are an expert AI municipal building code compliance officer. "
        "Evaluate the user's design query strictly and exclusively against the provided "
        "enterprise municipal code chunks. Output:\n"
        "1. Compliance Status: PASS, FAIL, or NEEDS REVIEW.\n"
        "2. Detailed Reasoning: Grounded solely in the provided context chunks.\n"
        "3. Exact Legal Citations / Segment references.\n"
        "Do not hallucinate or extrapolate beyond the provided text."
    )
    
    user_message = (
        f"Design Query: {query_text}\n\n"
        f"Retrieved Enterprise Code Context:\n{context_str}"
    )
    
    response = claude_client.messages.create(
        model="claude-sonnet-5",
        max_tokens=1000,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}]
    )
    
    return response.content[0].text

if __name__ == "__main__":
    test_query = "What are the requirements for exterior walls and bay windows?"
    report = evaluate_compliance(test_query)
    print("\n" + "="*60 + "\nENTERPRISE RAG COMPLIANCE REPORT:\n" + "="*60)
    print(report)