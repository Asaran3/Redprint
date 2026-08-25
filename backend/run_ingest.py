from ingest import ingest_pdf_code

if __name__ == "__main__":
    ingest_pdf_code(
        file_path="SampleCodeDoc.pdf", 
        city_name="San Francisco", 
        code_section="Chapter 10 - Means of Egress"
    )