# Raksha — SQLite Audit Store + Evidence Package
# Provides legal-admissibility audit trail for every case analyzed.

from __future__ import annotations
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

from sqlalchemy import create_engine, Column, String, Float, Text, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker, Session

logger = logging.getLogger("raksha.store")

Base = declarative_base()

# Database path — same directory as the backend
DB_DIR = Path(__file__).parent.parent.parent / "data"
DB_PATH = DB_DIR / "raksha_audit.db"


class CaseRecord(Base):
    """SQLAlchemy model for the audit/evidence store."""
    __tablename__ = "cases"

    case_id = Column(String, primary_key=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    input_text = Column(Text, nullable=False)
    language = Column(String(5), default="en")
    label = Column(String(20), nullable=False)
    scam_type = Column(String(50), nullable=True)
    confidence = Column(Float, default=0.0)
    reasons = Column(Text, default="")
    signals = Column(Text, default="[]")  # JSON array
    model_used = Column(String(100), default="")
    full_response = Column(Text, default="{}")  # Full JSON response for evidence
    guidance_json = Column(Text, nullable=True)
    complaint_json = Column(Text, nullable=True)
    alert_json = Column(Text, nullable=True)


class AuditStore:
    """Manages the SQLite audit trail and evidence packages."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(f"sqlite:///{self.db_path}", echo=False)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)

    def _get_session(self) -> Session:
        return self.SessionLocal()

    def log_case(
        self,
        case_id: str,
        input_text: str,
        language: str,
        label: str,
        scam_type: Optional[str],
        confidence: float,
        reasons: str,
        signals: list[str],
        model_used: str,
        full_response: dict,
        guidance_json: Optional[str] = None,
        complaint_json: Optional[str] = None,
        alert_json: Optional[str] = None,
    ) -> CaseRecord:
        """Log a case to the audit trail."""
        session = self._get_session()
        try:
            record = CaseRecord(
                case_id=case_id,
                timestamp=datetime.now(timezone.utc),
                input_text=input_text,
                language=language,
                label=label,
                scam_type=scam_type,
                confidence=confidence,
                reasons=reasons,
                signals=json.dumps(signals),
                model_used=model_used,
                full_response=json.dumps(full_response),
                guidance_json=guidance_json,
                complaint_json=complaint_json,
                alert_json=alert_json,
            )
            session.add(record)
            session.commit()
            session.refresh(record)
            logger.info(f"Case logged: {case_id} | {label} | {scam_type}")
            return record
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to log case {case_id}: {e}")
            raise
        finally:
            session.close()

    def get_case(self, case_id: str) -> Optional[CaseRecord]:
        """Retrieve a single case by ID."""
        session = self._get_session()
        try:
            return session.query(CaseRecord).filter(CaseRecord.case_id == case_id).first()
        finally:
            session.close()

    def list_cases(self, limit: int = 100, offset: int = 0) -> list[CaseRecord]:
        """List cases, most recent first."""
        session = self._get_session()
        try:
            return (
                session.query(CaseRecord)
                .order_by(CaseRecord.timestamp.desc())
                .offset(offset)
                .limit(limit)
                .all()
            )
        finally:
            session.close()

    def count_cases(self) -> int:
        """Count total cases."""
        session = self._get_session()
        try:
            return session.query(CaseRecord).count()
        finally:
            session.close()

    def get_evidence_package(self, case_id: str) -> Optional[dict]:
        """Generate a downloadable evidence package for a case."""
        record = self.get_case(case_id)
        if not record:
            return None

        package = {
            "evidence_package_version": "1.0",
            "case_id": record.case_id,
            "generated_at": datetime.now(timezone.utc).isoformat() + "Z",
            "case_timestamp": record.timestamp.isoformat() + "Z" if record.timestamp else None,
            "input_text": record.input_text,
            "language_detected": record.language,
            "classification": {
                "label": record.label,
                "scam_type": record.scam_type,
                "confidence": record.confidence,
                "reasons": record.reasons,
                "signals": json.loads(record.signals) if record.signals else [],
            },
            "model_used": record.model_used,
            "full_response": json.loads(record.full_response) if record.full_response else {},
            "guidance": json.loads(record.guidance_json) if record.guidance_json else None,
            "complaint_draft": json.loads(record.complaint_json) if record.complaint_json else None,
            "authority_alert": json.loads(record.alert_json) if record.alert_json else None,
            "audit_note": "This evidence package is auto-generated by Raksha for audit and legal-admissibility purposes.",
        }
        return package


# Singleton
_store: Optional[AuditStore] = None


def get_store() -> AuditStore:
    """Get the singleton audit store instance."""
    global _store
    if _store is None:
        _store = AuditStore()
    return _store
