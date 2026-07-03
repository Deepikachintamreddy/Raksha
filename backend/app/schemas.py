# Raksha — Pydantic Schemas (Frozen API Contracts)
# These are THE contracts. Frontend builds against them; backend fills them.
# Do NOT change without team sign-off.

from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional
from uuid import uuid4
from datetime import datetime, timezone


# ─── Request Models ───

class UserDetails(BaseModel):
    amount_lost: Optional[str] = None
    datetime: Optional[str] = None
    suspect_phone: Optional[str] = None
    suspect_upi: Optional[str] = None
    platform: Optional[str] = None


class AnalyzeRequest(BaseModel):
    text: str
    user_details: Optional[UserDetails] = None


# ─── Agent Output Models ───

class ClassificationResult(BaseModel):
    label: str = Field(..., pattern=r"^(SCAM|SAFE|UNCERTAIN)$")
    scam_type: Optional[str] = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    signals: list[str] = Field(default_factory=list)
    reasons: str = ""


class ReportTo(BaseModel):
    helpline: str = "1930"
    portal: str = "cybercrime.gov.in"


class GuidanceResult(BaseModel):
    headline: str
    immediate_action: str
    steps: list[str] = Field(default_factory=list)
    key_facts: list[str] = Field(default_factory=list)
    report_to: ReportTo = Field(default_factory=ReportTo)


class SuspectIdentifiers(BaseModel):
    phone: Optional[str] = None
    upi_or_account: Optional[str] = None
    platform: Optional[str] = None
    links: Optional[str] = None
    channel: Optional[str] = None


class ComplaintDraft(BaseModel):
    category: str
    incident_datetime: str = "[to be filled by complainant]"
    amount_involved: str = "No financial loss reported"
    suspect_identifiers: SuspectIdentifiers = Field(default_factory=SuspectIdentifiers)
    narrative: str
    evidence_checklist: list[str] = Field(default_factory=list)
    where_to_submit: str = "File at cybercrime.gov.in or call 1930. For financial loss, call 1930 immediately."
    disclaimer: str = "This is an auto-generated draft for your review. Verify all details before submitting."


class AuthorityAlert(BaseModel):
    alert_id: str = Field(default_factory=lambda: str(uuid4()))
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
    scam_type: str
    severity: str = Field(default="medium", pattern=r"^(high|medium)$")
    confidence: float = Field(..., ge=0.0, le=1.0)
    suspect_identifiers: SuspectIdentifiers = Field(default_factory=SuspectIdentifiers)
    observed_signals: list[str] = Field(default_factory=list)
    recommended_routing: str = "MHA I4C / telecom abuse desk"
    audit_ref: Optional[str] = None
    privacy_note: str = "Contains potential PII; handle per data-protection norms."


# ─── Orchestrator Output ───

class OrchestratorAttachments(BaseModel):
    complaint_draft: Optional[ComplaintDraft] = None
    authority_alert: Optional[AuthorityAlert] = None


class OrchestratorOutput(BaseModel):
    language: str = Field(default="en", pattern=r"^(en|hi|te|kn)$")
    verdict: str = Field(..., pattern=r"^(SCAM|SAFE|UNCERTAIN)$")
    reply_text: str
    attachments: OrchestratorAttachments = Field(default_factory=OrchestratorAttachments)


# ─── API Response Models ───

class AnalyzeResponse(BaseModel):
    case_id: str = Field(default_factory=lambda: str(uuid4()))
    language: str = "en"
    verdict: str
    reply_text: str
    classification: ClassificationResult
    guidance: Optional[GuidanceResult] = None
    complaint_draft: Optional[ComplaintDraft] = None
    authority_alert: Optional[AuthorityAlert] = None


class ConfusionMatrix(BaseModel):
    labels: list[str] = Field(default_factory=lambda: ["SCAM", "SAFE", "UNCERTAIN"])
    matrix: list[list[int]] = Field(default_factory=lambda: [[0]*3 for _ in range(3)])


class ScamTypeMetrics(BaseModel):
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    count: int = 0


class MetricsResponse(BaseModel):
    n_test: int = 0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    false_positive_rate: float = 0.0
    confusion_matrix: ConfusionMatrix = Field(default_factory=ConfusionMatrix)
    by_scam_type: dict[str, ScamTypeMetrics] = Field(default_factory=dict)


class CaseResponse(BaseModel):
    case_id: str
    timestamp: str
    input: str
    language: str
    label: str
    scam_type: Optional[str] = None
    confidence: float
    reasons: str
    model: str = ""
    evidence_package_url: Optional[str] = None


class CaseListResponse(BaseModel):
    cases: list[CaseResponse] = Field(default_factory=list)
    total: int = 0
