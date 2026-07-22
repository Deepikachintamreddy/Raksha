# Raksha — SQLite Audit Store + Evidence Package
# Provides legal-admissibility audit trail for every case analyzed.
# v2.0: Tamper-evident hash chain + entity extraction support.

from __future__ import annotations
import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

from sqlalchemy import create_engine, Column, String, Float, Text, DateTime, Integer, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session

logger = logging.getLogger("raksha.store")

Base = declarative_base()

# Database path — same directory as the backend
DB_DIR = Path(__file__).parent.parent.parent / "data"
DB_PATH = DB_DIR / "raksha_audit.db"

# Prompt version identifiers for evidence packages
PROMPT_VERSIONS = {
    "classifier": "v2.0-explainability",
    "guidance": "v1.0",
    "complaint": "v1.0",
    "alert": "v1.0",
    "classifier_streaming": "v1.0",
}


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
    # v2.0: Hash chain columns for tamper-evident audit trail
    prev_hash = Column(String(64), nullable=True, default=None)
    record_hash = Column(String(64), nullable=True, default=None)


class CaseEntity(Base):
    """Extracted entities from cases for campaign intelligence."""
    __tablename__ = "case_entities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    case_id = Column(String, nullable=False, index=True)
    entity_type = Column(String(30), nullable=False)  # phone, upi, account, url, agency
    entity_value = Column(String(500), nullable=False)


class GuardianRecord(Base):
    """Trusted contacts registered by citizens."""
    __tablename__ = "guardians"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=False)
    relationship = Column(String(50), nullable=False)


class GuardianAlertRecord(Base):
    """Logs of alerts sent to guardians."""
    __tablename__ = "guardian_alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    case_id = Column(String(50), nullable=False)
    guardian_name = Column(String(100), nullable=False)
    guardian_phone = Column(String(20), nullable=False)
    message = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    status = Column(String(20), default="SENT")  # SENT or SIMULATED


class RehearsalRecord(Base):
    """Logs of safe training simulations completed by citizens."""
    __tablename__ = "rehearsals"

    session_id = Column(String(50), primary_key=True)
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)
    turns_count = Column(Integer, default=0)
    history = Column(Text, default="[]")  # JSON string
    scorecard = Column(Text, nullable=True)  # JSON string


def _compute_record_hash(prev_hash: Optional[str], case_data: dict) -> str:
    """Compute SHA-256 hash: sha256(prev_hash + canonical_json(case_data))."""
    canonical = json.dumps(case_data, sort_keys=True, ensure_ascii=False, default=str)
    payload = (prev_hash or "GENESIS") + canonical
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class AuditStore:
    """Manages the SQLite audit trail and evidence packages."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(f"sqlite:///{self.db_path}", echo=False)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        # Migrate old databases that lack hash columns
        self._migrate_hash_columns()

    def _migrate_hash_columns(self):
        """Add prev_hash and record_hash columns if they don't exist (migration)."""
        try:
            with self.engine.connect() as conn:
                # Check if columns exist by trying to select them
                try:
                    conn.execute(text("SELECT prev_hash FROM cases LIMIT 1"))
                except Exception:
                    conn.execute(text("ALTER TABLE cases ADD COLUMN prev_hash VARCHAR(64)"))
                    conn.commit()
                try:
                    conn.execute(text("SELECT record_hash FROM cases LIMIT 1"))
                except Exception:
                    conn.execute(text("ALTER TABLE cases ADD COLUMN record_hash VARCHAR(64)"))
                    conn.commit()
        except Exception as e:
            logger.debug(f"Hash column migration check: {e}")

    def _get_session(self) -> Session:
        return self.SessionLocal()

    def _get_last_hash(self, session: Session) -> Optional[str]:
        """Get the record_hash of the most recent case for chaining."""
        last = (
            session.query(CaseRecord.record_hash)
            .order_by(CaseRecord.timestamp.desc())
            .first()
        )
        return last[0] if last and last[0] else None

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
        """Log a case to the audit trail with hash chain."""
        session = self._get_session()
        try:
            now = datetime.now(timezone.utc)

            # Build canonical case data for hashing
            case_data = {
                "case_id": case_id,
                "timestamp": now.strftime("%Y-%m-%dT%H:%M:%S"),
                "input_text": input_text,
                "language": language,
                "label": label,
                "scam_type": scam_type,
                "confidence": confidence,
                "reasons": reasons,
                "signals": signals,
                "model_used": model_used,
            }

            # Get previous hash for chaining
            prev_hash = self._get_last_hash(session)
            record_hash = _compute_record_hash(prev_hash, case_data)

            record = CaseRecord(
                case_id=case_id,
                timestamp=now,
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
                prev_hash=prev_hash,
                record_hash=record_hash,
            )
            session.add(record)
            session.commit()
            session.refresh(record)
            logger.info(f"Case logged: {case_id} | {label} | {scam_type} | hash={record_hash[:12]}...")
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
        """Generate a downloadable evidence package for a case with hash chain."""
        record = self.get_case(case_id)
        if not record:
            return None

        import os
        model_name = record.model_used or os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest")

        package = {
            "evidence_package_version": "2.0",
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
            "model_info": {
                "model_name": model_name,
                "provider": os.getenv("LLM_PROVIDER", "gemini"),
            },
            "prompt_versions": PROMPT_VERSIONS,
            "full_response": json.loads(record.full_response) if record.full_response else {},
            "guidance": json.loads(record.guidance_json) if record.guidance_json else None,
            "complaint_draft": json.loads(record.complaint_json) if record.complaint_json else None,
            "authority_alert": json.loads(record.alert_json) if record.alert_json else None,
            "tamper_evident_chain": {
                "record_hash": record.record_hash,
                "prev_hash": record.prev_hash,
                "hash_algorithm": "SHA-256",
                "chain_description": (
                    "Each record's hash is computed as SHA-256(previous_record_hash + canonical_JSON(case_data)). "
                    "The first record in the chain uses 'GENESIS' as the previous hash. "
                    "Any modification to a record or its ordering will break the chain."
                ),
            },
            "chain_of_custody": {
                "collected_by": "Raksha AI System (automated)",
                "collection_method": "Real-time classification via Gemini LLM multi-agent pipeline",
                "storage": "SQLite audit database with SHA-256 hash chain",
                "integrity": "Tamper-evident hash chain — verify at GET /audit/verify",
                "notes": (
                    "This evidence package was auto-generated by the Raksha system at the time of analysis. "
                    "The hash chain ensures that no records have been modified, deleted, or reordered after creation. "
                    "For legal proceedings, verify the chain integrity using the /audit/verify endpoint."
                ),
            },
        }
        return package

    def verify_chain(self) -> dict:
        """Re-walk the entire hash chain and verify integrity."""
        session = self._get_session()
        try:
            records = (
                session.query(CaseRecord)
                .order_by(CaseRecord.timestamp.asc())
                .all()
            )

            if not records:
                return {"intact": True, "first_broken_record": None, "total_records": 0, "verified_records": 0}

            expected_prev_hash = None
            verified = 0

            for record in records:
                # Skip records without hashes (pre-v2.0 records)
                if record.record_hash is None:
                    expected_prev_hash = None
                    verified += 1
                    continue

                # Verify prev_hash matches expected
                if record.prev_hash != expected_prev_hash:
                    return {
                        "intact": False,
                        "first_broken_record": record.case_id,
                        "total_records": len(records),
                        "verified_records": verified,
                        "error": "prev_hash mismatch — chain link broken",
                    }

                # Recompute hash and verify
                case_data = {
                    "case_id": record.case_id,
                    "timestamp": record.timestamp.strftime("%Y-%m-%dT%H:%M:%S") if record.timestamp else "",
                    "input_text": record.input_text,
                    "language": record.language,
                    "label": record.label,
                    "scam_type": record.scam_type,
                    "confidence": record.confidence,
                    "reasons": record.reasons,
                    "signals": json.loads(record.signals) if record.signals else [],
                    "model_used": record.model_used,
                }
                expected_hash = _compute_record_hash(record.prev_hash, case_data)

                if expected_hash != record.record_hash:
                    return {
                        "intact": False,
                        "first_broken_record": record.case_id,
                        "total_records": len(records),
                        "verified_records": verified,
                        "error": "record_hash mismatch — record content was tampered",
                    }

                expected_prev_hash = record.record_hash
                verified += 1

            return {
                "intact": True,
                "first_broken_record": None,
                "total_records": len(records),
                "verified_records": verified,
            }
        finally:
            session.close()

    # ── Entity methods for Campaign Intelligence ──

    def log_entities(self, case_id: str, entities: list[dict]):
        """Log extracted entities for a case. Each entity: {type, value}."""
        session = self._get_session()
        try:
            for ent in entities:
                record = CaseEntity(
                    case_id=case_id,
                    entity_type=ent["type"],
                    entity_value=ent["value"],
                )
                session.add(record)
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to log entities for {case_id}: {e}")
        finally:
            session.close()

    def get_all_entities(self) -> list[CaseEntity]:
        """Get all case entities for campaign analysis."""
        session = self._get_session()
        try:
            return session.query(CaseEntity).all()
        finally:
            session.close()

    def get_entities_for_case(self, case_id: str) -> list[CaseEntity]:
        """Get entities for a specific case."""
        session = self._get_session()
        try:
            return session.query(CaseEntity).filter(CaseEntity.case_id == case_id).all()
        finally:
            session.close()

    def get_all_cases_asc(self) -> list[CaseRecord]:
        """Get all cases ordered by timestamp ascending (for campaign analysis)."""
        session = self._get_session()
        try:
            return session.query(CaseRecord).order_by(CaseRecord.timestamp.asc()).all()
        finally:
            session.close()

    # ── Guardian methods ──
    def add_guardian(self, name: str, phone: str, relationship: str) -> GuardianRecord:
        """Register a new trusted contact."""
        session = self._get_session()
        try:
            record = GuardianRecord(name=name, phone=phone, relationship=relationship)
            session.add(record)
            session.commit()
            session.refresh(record)
            return record
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to add guardian: {e}")
            raise
        finally:
            session.close()

    def get_guardians(self) -> list[GuardianRecord]:
        """Get all registered trusted contacts."""
        session = self._get_session()
        try:
            return session.query(GuardianRecord).all()
        finally:
            session.close()

    def delete_guardian(self, guardian_id: int) -> bool:
        """Delete a registered trusted contact."""
        session = self._get_session()
        try:
            record = session.query(GuardianRecord).filter(GuardianRecord.id == guardian_id).first()
            if record:
                session.delete(record)
                session.commit()
                return True
            return False
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to delete guardian {guardian_id}: {e}")
            return False
        finally:
            session.close()

    # ── Guardian Alert methods ──
    def log_guardian_alert(
        self, case_id: str, guardian_name: str, guardian_phone: str, message: str, status: str
    ) -> GuardianAlertRecord:
        """Log a sent or simulated guardian alert."""
        session = self._get_session()
        try:
            record = GuardianAlertRecord(
                case_id=case_id,
                guardian_name=guardian_name,
                guardian_phone=guardian_phone,
                message=message,
                status=status,
            )
            session.add(record)
            session.commit()
            session.refresh(record)
            return record
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to log guardian alert: {e}")
            raise
        finally:
            session.close()

    def get_guardian_alerts(self) -> list[GuardianAlertRecord]:
        """Get all guardian alerts, most recent first."""
        session = self._get_session()
        try:
            return session.query(GuardianAlertRecord).order_by(GuardianAlertRecord.timestamp.desc()).all()
        finally:
            session.close()

    # ── Rehearsal methods ──
    def start_rehearsal(self, session_id: str) -> RehearsalRecord:
        """Start a new simulation rehearsal session."""
        session = self._get_session()
        try:
            record = RehearsalRecord(session_id=session_id)
            session.add(record)
            session.commit()
            session.refresh(record)
            return record
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to start rehearsal {session_id}: {e}")
            raise
        finally:
            session.close()

    def update_rehearsal(self, session_id: str, history: list[dict], turns_count: int) -> Optional[RehearsalRecord]:
        """Update message history of a rehearsal session."""
        session = self._get_session()
        try:
            record = session.query(RehearsalRecord).filter(RehearsalRecord.session_id == session_id).first()
            if record:
                record.history = json.dumps(history)
                record.turns_count = turns_count
                session.commit()
                session.refresh(record)
                return record
            return None
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to update rehearsal {session_id}: {e}")
            raise
        finally:
            session.close()

    def complete_rehearsal(self, session_id: str, scorecard: dict) -> Optional[RehearsalRecord]:
        """Complete a rehearsal session with a scorecard."""
        session = self._get_session()
        try:
            record = session.query(RehearsalRecord).filter(RehearsalRecord.session_id == session_id).first()
            if record:
                record.completed_at = datetime.now(timezone.utc)
                record.scorecard = json.dumps(scorecard)
                session.commit()
                session.refresh(record)
                return record
            return None
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to complete rehearsal {session_id}: {e}")
            raise
        finally:
            session.close()

    def count_completed_rehearsals(self) -> int:
        """Count total completed (inoculated) rehearsals."""
        session = self._get_session()
        try:
            return session.query(RehearsalRecord).filter(RehearsalRecord.completed_at != None).count()
        finally:
            session.close()


# Singleton
_store: Optional[AuditStore] = None


def get_store() -> AuditStore:
    """Get the singleton audit store instance."""
    global _store
    if _store is None:
        _store = AuditStore()
    return _store
