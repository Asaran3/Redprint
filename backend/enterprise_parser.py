import os
import json
import re
import numpy as np
from openai import OpenAI
import pymupdf  # Modern PyMuPDF import
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def get_embedding(text: str):
    """Generates an embedding vector for semantic distance checking."""
    response = client.embeddings.create(
        input=[text],
        model="text-embedding-3-small"
    )
    return response.data[0].embedding

def cosine_similarity(vec_a, vec_b):
    """Calculates cosine similarity between two embedding vectors."""
    a = np.array(vec_a)
    b = np.array(vec_b)
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def is_noise_block(text: str) -> bool:
    """
    IMPLEMENTATION 1: Noise Filter. 
    Discards page numbers, short snippets, and boilerplate header titles 
    to ensure only substantive regulatory text is indexed.
    """
    cleaned = text.strip()
    if len(cleaned) < 45:
        return True
    if re.match(r'^(page\s*\d+|\d+\s*of\s*\d+|california\s*energy\s*code|title\s*24)', cleaned, re.IGNORECASE):
        return True
    return False

def llm_assisted_structure_mapping(pdf_path: str) -> dict:
    """Extracts the first few pages to build a structured map of sections and expected content."""
    doc = pymupdf.open(pdf_path)
    front_matter_text = ""
    for page_num in range(min(4, len(doc))):
        front_matter_text += f"\n--- PAGE {page_num + 1} ---\n" + doc[page_num].get_text("text")

    system_prompt = (
        "You are an expert legal document parser. Analyze the table of contents or front matter "
        "of a building code document. Output a JSON object mapping the document's sections and titles."
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Document Front Matter:\n{front_matter_text}"}
            ],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception:
        return {}

def semantic_boundary_chunking(blocks: list, similarity_threshold: float = 0.72) -> list:
    """
    IMPLEMENTATION 2: Full-Paragraph & Semantic Boundary Enforcement.
    Splits chunks dynamically when topic similarity drops or paragraph length grows complete.
    """
    if not blocks:
        return []

    chunks = []
    current_chunk = blocks[0]
    prev_embedding = get_embedding(current_chunk)

    for block_text in blocks[1:]:
        curr_embedding = get_embedding(block_text)
        similarity = cosine_similarity(prev_embedding, curr_embedding)

        # Split if semantic shift occurs or chunk size is comprehensive
        if similarity < similarity_threshold or len(current_chunk) > 1200:
            if len(current_chunk.strip()) > 60:
                chunks.append(current_chunk.strip())
            current_chunk = block_text
        else:
            current_chunk += "\n\n" + block_text
            
        prev_embedding = curr_embedding

    if current_chunk.strip() and len(current_chunk.strip()) > 60:
        chunks.append(current_chunk.strip())

    return chunks

def parse_pdf_enterprise(pdf_path: str, city_name: str) -> list:
    """
    IMPLEMENTATION 3: Hybrid Enterprise Parsing Pipeline.
    Combines structure mapping, noise filtering, and context metadata binding.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"File not found: {pdf_path}")

    print("Step 1: Running LLM Structure Mapping...")
    structure_map = llm_assisted_structure_mapping(pdf_path)

    print("Step 2: Extracting layout blocks with PyMuPDF and applying Noise Filters...")
    doc = pymupdf.open(pdf_path)
    raw_blocks = []
    current_section = "General Provisions / Title 24"

    for page_num, page in enumerate(doc, 1):
        blocks = page.get_text("blocks")
        for b in blocks:
            text = b[4].strip()
            
            # Detect section headers to bind context
            header_match = re.search(r'(SECTION\s+[\d\.\-]+[^\n]+)', text, re.IGNORECASE)
            if header_match:
                current_section = header_match.group(1)
                continue

            # Apply Implementation 1
            if is_noise_block(text):
                continue

            # Apply Implementation 3: Contextual Metadata Binding
            enriched_block = f"Jurisdiction: {city_name} | Section: {current_section} | Content: {text}"
            raw_blocks.append(enriched_block)

    print("Step 3: Executing Semantic Boundary Detection for Substantive Paragraphs...")
    segmented_chunks = semantic_boundary_chunking(raw_blocks, similarity_threshold=0.72)

    enriched_output = []
    for idx, chunk in enumerate(segmented_chunks):
        enriched_output.append({
            "chunk_id": idx + 1,
            "city": city_name,
            "section": current_section,
            "content": chunk
        })

    print(f"Enterprise parsing complete. Generated {len(enriched_output)} substantive chunks.")
    return enriched_output