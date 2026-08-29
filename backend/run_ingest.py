from pathlib import Path

from ingest import run_smart_ingestion

if __name__ == "__main__":
    # Run the updated enterprise smart ingestion pipeline
    run_smart_ingestion("SampleCodeDoc.pdf", city_name="San Francisco")