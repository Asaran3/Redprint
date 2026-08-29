import base64

import pymupdf

MAX_PAGES = 8
RENDER_SCALE = 1.35
MAX_TEXT_CHARS = 24000


def extract_blueprint(pdf_bytes: bytes) -> dict:
    """Pull sheet text and page images from a submitted plan set."""
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    page_count = len(doc)
    text_parts: list[str] = []
    images: list[dict] = []

    for index, page in enumerate(doc):
        page_no = index + 1
        page_text = (page.get_text("text") or "").strip()
        if page_text:
            text_parts.append(f"--- Sheet {page_no} ---\n{page_text}")

        if index < MAX_PAGES:
            pixmap = page.get_pixmap(matrix=pymupdf.Matrix(RENDER_SCALE, RENDER_SCALE))
            jpeg_bytes = pixmap.tobytes("jpeg")
            images.append(
                {
                    "page": page_no,
                    "media_type": "image/jpeg",
                    "data": base64.b64encode(jpeg_bytes).decode("ascii"),
                }
            )

    doc.close()
    combined = "\n\n".join(text_parts)
    if len(combined) > MAX_TEXT_CHARS:
        combined = combined[:MAX_TEXT_CHARS] + "\n\n[Plan text truncated]"

    return {
        "page_count": page_count,
        "pages_imaged": len(images),
        "text": combined,
        "images": images,
    }
