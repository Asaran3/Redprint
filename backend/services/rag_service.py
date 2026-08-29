import json
import re

import anthropic
from openai import OpenAI
from sqlalchemy import text

from config import settings
from database import engine
from schemas import ComplianceReport, Coverage, Finding, Jurisdiction

openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
claude_client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

REVIEW_DOMAINS = [
    "zoning setbacks lot coverage floor area ratio site plan",
    "building height stories occupancy group construction type",
    "means of egress exit width travel distance stairways",
    "fire protection fire rating occupancy separation sprinklers",
    "accessibility ADA path of travel restrooms parking stalls",
    "parking loading bicycle spaces driveway width",
    "energy Title 24 insulation windows mechanical",
    "structural foundation seismic walls roof live loads",
    "plumbing fixtures water closets ventilation",
    "life safety smoke alarms emergency lighting",
]


def _embed(query_text: str) -> list[float]:
    response = openai_client.embeddings.create(
        input=[query_text],
        model="text-embedding-3-small",
    )
    return response.data[0].embedding


def retrieve_code_chunks(query_text: str, city: str = "", top_k: int = 4) -> list[dict]:
    query_embedding = str(_embed(query_text))
    city_filter = f"%{city.strip()}%" if city.strip() else "%"

    sql = text(
        """
        SELECT city_name, code_section, chunk_text,
               (embedding <=> :query_emb) AS distance
        FROM municipal_codes
        WHERE city_name ILIKE :city
        ORDER BY distance ASC
        LIMIT :limit
        """
    )
    fallback_sql = text(
        """
        SELECT city_name, code_section, chunk_text,
               (embedding <=> :query_emb) AS distance
        FROM municipal_codes
        ORDER BY distance ASC
        LIMIT :limit
        """
    )

    with engine.connect() as connection:
        rows = connection.execute(
            sql,
            {"query_emb": query_embedding, "city": city_filter, "limit": top_k},
        ).fetchall()
        used_filter = city or "none"
        if not rows:
            rows = connection.execute(
                fallback_sql,
                {"query_emb": query_embedding, "limit": top_k},
            ).fetchall()
            used_filter = "unfiltered-fallback"

    return [
        {
            "city": row[0],
            "section": row[1],
            "text": row[2],
            "distance": float(row[3]) if row[3] is not None else 1.0,
            "filter": used_filter,
        }
        for row in rows
    ]


def retrieve_codes_for_blueprint(blueprint_text: str, city: str) -> tuple[list[dict], str]:
    queries = list(REVIEW_DOMAINS)
    keywords = re.findall(r"[A-Za-z][A-Za-z0-9\-]{3,}", blueprint_text[:4000])
    if keywords:
        queries.append(" ".join(dict.fromkeys(keywords[:40])))

    embedded = openai_client.embeddings.create(
        input=queries,
        model="text-embedding-3-small",
    )
    vectors = [item.embedding for item in embedded.data]

    seen: set[str] = set()
    merged: list[dict] = []
    filter_used = city or "none"
    city_filter = f"%{city.strip()}%" if city.strip() else "%"

    sql = text(
        """
        SELECT city_name, code_section, chunk_text,
               (embedding <=> :query_emb) AS distance
        FROM municipal_codes
        WHERE city_name ILIKE :city
        ORDER BY distance ASC
        LIMIT :limit
        """
    )
    fallback_sql = text(
        """
        SELECT city_name, code_section, chunk_text,
               (embedding <=> :query_emb) AS distance
        FROM municipal_codes
        ORDER BY distance ASC
        LIMIT :limit
        """
    )

    with engine.connect() as connection:
        for vector in vectors:
            query_emb = str(vector)
            rows = connection.execute(
                sql,
                {"query_emb": query_emb, "city": city_filter, "limit": 3},
            ).fetchall()
            used = city or "none"
            if not rows:
                rows = connection.execute(
                    fallback_sql,
                    {"query_emb": query_emb, "limit": 3},
                ).fetchall()
                used = "unfiltered-fallback"
            if used == "unfiltered-fallback":
                filter_used = used
            for row in rows:
                chunk = {
                    "city": row[0],
                    "section": row[1],
                    "text": row[2],
                    "distance": float(row[3]) if row[3] is not None else 1.0,
                    "filter": used,
                }
                key = (chunk["section"] or "") + (chunk["text"] or "")[:240]
                if key in seen:
                    continue
                seen.add(key)
                merged.append(chunk)
            if len(merged) >= 24:
                break

    return merged, filter_used


def _format_code_context(chunks: list[dict]) -> str:
    parts = []
    for i, chunk in enumerate(chunks, 1):
        similarity = 1 - chunk["distance"]
        parts.append(
            f"--- Source [{i}] (similarity {similarity:.3f}) ---\n"
            f"Jurisdiction: {chunk['city']} | Section: {chunk['section']}\n"
            f"{chunk['text']}"
        )
    return "\n\n".join(parts) if parts else "No municipal code chunks were retrieved."


def _parse_model_json(raw: str) -> dict:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        data = json.loads(cleaned[start : end + 1])
        if isinstance(data, dict):
            return data
    raise json.JSONDecodeError("No JSON object in model output", cleaned, 0)


def generate_full_report(
    *,
    filename: str,
    jurisdiction: dict,
    blueprint: dict,
) -> ComplianceReport:
    city = jurisdiction.get("city") or ""
    chunks, filter_used = retrieve_codes_for_blueprint(blueprint.get("text") or "", city)
    code_context = _format_code_context(chunks)

    system_prompt = (
        "You are a municipal plans examiner. The user submitted a full blueprint "
        "and a property location. Produce a whole-set compliance report, not answers "
        "to a user question.\n\n"
        "Rules:\n"
        "1. Review every observable aspect of the plans: zoning/site, height, occupancy, "
        "egress, fire, accessibility, parking, energy, structural notes, plumbing/fixtures, "
        "and life safety.\n"
        "2. Cite ONLY the provided municipal code chunks. If a topic is visible on the "
        "plans but no matching code chunk was retrieved, status INSUFFICIENT_EVIDENCE.\n"
        "3. If the plans do not show enough to judge a topic, status INSUFFICIENT_EVIDENCE. "
        "Never invent dimensions, ratings, or code sections.\n"
        "4. NONCOMPLIANT only when the plans conflict with a cited retrieved code.\n"
        "5. Return JSON only matching the schema."
    )

    user_payload = {
        "property": jurisdiction,
        "blueprint_filename": filename,
        "extracted_plan_text": blueprint.get("text") or "(no extractable text)",
        "retrieved_municipal_codes": code_context,
        "output_schema": {
            "overall_status": "PASS | FAIL | MIXED | INSUFFICIENT_EVIDENCE",
            "executive_summary": "string",
            "findings": [
                {
                    "category": "string",
                    "status": "COMPLIANT | NONCOMPLIANT | INSUFFICIENT_EVIDENCE | NOT_APPLICABLE",
                    "title": "string",
                    "observation": "what the plans show",
                    "code_citation": "section from retrieved sources only",
                    "code_excerpt": "short quote from retrieved sources only",
                    "recommendation": "string",
                    "sheet_hint": "sheet/page if known",
                }
            ],
            "coverage_notes": "what could not be checked",
        },
    }

    content: list[dict] = [
        {
            "type": "text",
            "text": json.dumps(user_payload, ensure_ascii=False)[:50000],
        }
    ]
    for image in blueprint.get("images") or []:
        content.append(
            {
                "type": "text",
                "text": f"Blueprint sheet {image['page']}:",
            }
        )
        content.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": image["media_type"],
                    "data": image["data"],
                },
            }
        )

    response = claude_client.messages.create(
        model="claude-sonnet-5",
        max_tokens=4096,
        thinking={"type": "disabled"},
        system=system_prompt + " Reply with a single JSON object and no other text.",
        messages=[{"role": "user", "content": content}],
    )

    raw_bits = [
        block.text
        for block in response.content
        if getattr(block, "type", None) == "text" and getattr(block, "text", None)
    ]
    raw = "\n".join(raw_bits).strip()
    if not raw:
        raise ValueError(
            "Compliance model returned no text output. "
            f"blocks={[getattr(b, 'type', type(b).__name__) for b in response.content]}"
        )
    try:
        parsed = _parse_model_json(raw)
    except json.JSONDecodeError as exc:
        preview = raw[:500].replace("\n", " ")
        raise json.JSONDecodeError(
            f"No JSON object in model output: {preview}",
            raw,
            0,
        ) from exc
    findings: list[Finding] = []
    for item in parsed.get("findings") or []:
        if not isinstance(item, dict):
            continue
        try:
            findings.append(Finding.model_validate(item))
        except Exception:
            continue
    overall = parsed.get("overall_status") or "INSUFFICIENT_EVIDENCE"
    if overall not in {"PASS", "FAIL", "MIXED", "INSUFFICIENT_EVIDENCE"}:
        overall = "INSUFFICIENT_EVIDENCE"

    coverage_notes = parsed.get("coverage_notes") or ""
    if filter_used == "unfiltered-fallback":
        coverage_notes = (
            "No city-tagged codes matched this address; retrieval fell back to the "
            "full municipal library. " + coverage_notes
        ).strip()

    return ComplianceReport(
        filename=filename,
        jurisdiction=Jurisdiction(
            city=jurisdiction.get("city") or "Unknown",
            county=jurisdiction.get("county") or "",
            state=jurisdiction.get("state") or "",
            postal_code=jurisdiction.get("postal_code") or "",
            display_name=jurisdiction.get("display_name"),
            lat=jurisdiction.get("lat"),
            lon=jurisdiction.get("lon"),
        ),
        overall_status=overall,
        executive_summary=parsed.get("executive_summary") or "",
        findings=findings,
        coverage=Coverage(
            pages_reviewed=blueprint.get("pages_imaged") or 0,
            code_chunks_used=len(chunks),
            jurisdiction_filter=filter_used,
            notes=coverage_notes,
        ),
    )
