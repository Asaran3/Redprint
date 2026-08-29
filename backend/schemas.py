from typing import Literal, Optional

from pydantic import BaseModel, Field


FindingStatus = Literal[
    "COMPLIANT",
    "NONCOMPLIANT",
    "INSUFFICIENT_EVIDENCE",
    "NOT_APPLICABLE",
]
OverallStatus = Literal["PASS", "FAIL", "MIXED", "INSUFFICIENT_EVIDENCE"]


class Jurisdiction(BaseModel):
    city: str
    county: str = ""
    state: str = ""
    postal_code: str = ""
    display_name: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None


class Finding(BaseModel):
    category: str
    status: FindingStatus
    title: str
    observation: str = Field(
        description="What is visible on the submitted blueprint."
    )
    code_citation: str = ""
    code_excerpt: str = ""
    recommendation: str = ""
    sheet_hint: str = ""


class Coverage(BaseModel):
    pages_reviewed: int = 0
    code_chunks_used: int = 0
    jurisdiction_filter: str = ""
    notes: str = ""


class ComplianceReport(BaseModel):
    filename: str
    jurisdiction: Jurisdiction
    overall_status: OverallStatus
    executive_summary: str
    findings: list[Finding]
    coverage: Coverage
