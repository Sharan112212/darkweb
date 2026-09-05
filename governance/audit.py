import hashlib
import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class AuditRecord(BaseModel):
    event_id: str
    request_id: str
    user_id: str
    user_role: str
    action: str
    object_id: str
    timestamp: str
    details: Dict[str, Any] = Field(default_factory=dict)
    previous_event_hash: str
    event_hash: str

class TamperEvidentAuditChain:
    """
    Tamper-Evident Audit Event Chain (EC-27).
    Appends audit events with cryptographic hash chaining:
      event_hash = SHA256(previous_event_hash + event_id + request_id + action + object_id + timestamp + details_json)
    Provides verify_integrity() to detect any modification, deletion, or insertion.
    """

    GENESIS_HASH = "0000000000000000000000000000000000000000000000000000000000000000"

    def __init__(self):
        self._records: List[AuditRecord] = []

    def append(
        self,
        request_id: str,
        user_id: str,
        user_role: str,
        action: str,
        object_id: str,
        details: Optional[Dict[str, Any]] = None
    ) -> AuditRecord:
        now = datetime.now(timezone.utc).isoformat()
        prev_hash = self._records[-1].event_hash if self._records else self.GENESIS_HASH
        event_id = f"aud_{hashlib.sha256(f'{request_id}_{action}_{object_id}_{now}'.encode()).hexdigest()[:12]}"
        details_dict = details or {}
        details_json = json.dumps(details_dict, sort_keys=True)

        payload = f"{prev_hash}|{event_id}|{request_id}|{user_id}|{user_role}|{action}|{object_id}|{now}|{details_json}"
        event_hash = hashlib.sha256(payload.encode()).hexdigest()

        record = AuditRecord(
            event_id=event_id,
            request_id=request_id,
            user_id=user_id,
            user_role=user_role,
            action=action,
            object_id=object_id,
            timestamp=now,
            details=details_dict,
            previous_event_hash=prev_hash,
            event_hash=event_hash
        )
        self._records.append(record)
        return record

    def list_events(self, user_id: Optional[str] = None, object_id: Optional[str] = None) -> List[AuditRecord]:
        records = self._records
        if user_id:
            records = [r for r in records if r.user_id == user_id]
        if object_id:
            records = [r for r in records if r.object_id == object_id]
        return records

    def verify_integrity(self) -> Tuple_Bool_Reason:
        """
        Verifies the complete hash chain from Genesis to the tip.
        Detects tampering, out-of-order records, or deleted entries.
        """
        prev_hash = self.GENESIS_HASH
        for idx, rec in enumerate(self._records):
            if rec.previous_event_hash != prev_hash:
                return False, f"Integrity check failed at record index {idx} ({rec.event_id}): previous_hash mismatch."
            
            details_json = json.dumps(rec.details, sort_keys=True)
            payload = f"{rec.previous_event_hash}|{rec.event_id}|{rec.request_id}|{rec.user_id}|{rec.user_role}|{rec.action}|{rec.object_id}|{rec.timestamp}|{details_json}"
            expected_hash = hashlib.sha256(payload.encode()).hexdigest()

            if rec.event_hash != expected_hash:
                return False, f"Integrity check failed at record index {idx} ({rec.event_id}): event_hash mismatch."

            prev_hash = rec.event_hash

        return True, f"Chain integrity verified across all {len(self._records)} records."

class Tuple_Bool_Reason(tuple):
    pass

AuditStore = TamperEvidentAuditChain
