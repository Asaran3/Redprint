import time
import requests
from typing import Dict, Any

def resolve_jurisdiction(address: str) -> Dict[str, Any]:
    """
    Resolves a user-submitted property address to its local municipality, state, 
    postal code, and geographic coordinates with enterprise-grade error handling.
    """
    cleaned_address = address.strip()
    if not cleaned_address:
        return {"error": "Address string cannot be empty."}

    url = "https://nominatim.openstreetmap.org/search"
    headers = {"User-Agent": "RedprintComplianceChecker/1.0 (contact: redprint-local-dev)"}

    def search(query: str) -> list:
        response = requests.get(
            url,
            params={
                "q": query,
                "format": "json",
                "addressdetails": 1,
                "limit": 1,
                "countrycodes": "us",
            },
            headers=headers,
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    try:
        queries = [cleaned_address]
        if "usa" not in cleaned_address.lower() and "united states" not in cleaned_address.lower():
            queries.append(f"{cleaned_address}, USA")
        # City-level fallback: last two comma parts, or the whole string if no street hit
        parts = [p.strip() for p in cleaned_address.split(",") if p.strip()]
        if len(parts) >= 2:
            queries.append(", ".join(parts[-2:]) + ", USA")

        results = []
        for index, query in enumerate(queries):
            if index:
                time.sleep(1)
            results = search(query)
            if results:
                break

        if not results:
            return {"error": f"No geographic matches found for address: '{cleaned_address}'"}
            
        data = results[0]
        address_details = data.get("address", {})
        
        # Extract specific municipal boundaries with fallback hierarchy
        city = (
            address_details.get("city") or 
            address_details.get("town") or 
            address_details.get("village") or 
            address_details.get("municipality") or 
            "Unknown Municipality"
        )
        state = address_details.get("state", "California")
        postal_code = address_details.get("postcode", "")
        county = address_details.get("county", "")
        
        return {
            "success": True,
            "city": city,
            "county": county,
            "state": state,
            "postal_code": postal_code,
            "display_name": data.get("display_name"),
            "lat": float(data["lat"]),
            "lon": float(data["lon"])
        }
        
    except requests.exceptions.RequestException as e:
        return {"error": f"Geocoding service connection failed: {str(e)}"}

if __name__ == "__main__":
    test_address = "100 S Murphy St, Sunnyvale, CA"
    print(resolve_jurisdiction(test_address))