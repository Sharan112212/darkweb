import hashlib
from datetime import datetime, timezone
from typing import List, Dict, Optional
from pydantic import BaseModel, Field

class CaseNote(BaseModel):
    note_id: str
    author: str
    text: str
    timestamp: str

class Case(BaseModel):
    case_id: str
    name: str
    description: str
    created_by: str
    status: str = "open"  # open | under_review | closed | archived
    actor_ids: List[str] = Field(default_factory=list)
    link_ids: List[str] = Field(default_factory=list)
    evidence_ids: List[str] = Field(default_factory=list)
    notes: List[CaseNote] = Field(default_factory=list)
    legal_hold: bool = False
    created_at: str
    updated_at: str

class CaseManager:
    """
    Case Management Engine.
    Creates and manages cases with actor, link, and evidence references.
    Stores entity REFERENCES, not mutable copies, ensuring decision history is preserved.
    """

    def __init__(self):
        self._cases: Dict[str, Case] = {}

    def create_case(
        self,
        name: str,
        description: str,
        created_by: str,
        actor_ids: Optional[List[str]] = None,
        link_ids: Optional[List[str]] = None,
        evidence_ids: Optional[List[str]] = None
    ) -> Case:
        now = datetime.now(timezone.utc).isoformat()
        cid_hash = hashlib.sha256(f"{name}_{created_by}_{now}".encode()).hexdigest()[:12]
        case_id = f"case_{cid_hash}"

        case = Case(
            case_id=case_id,
            name=name,
            description=description,
            created_by=created_by,
            status="open",
            actor_ids=list(set(actor_ids or [])),
            link_ids=list(set(link_ids or [])),
            evidence_ids=list(set(evidence_ids or [])),
            notes=[],
            legal_hold=False,
            created_at=now,
            updated_at=now
        )
        self._cases[case_id] = case
        return case

    def get_case(self, case_id: str) -> Optional[Case]:
        return self._cases.get(case_id)

    def add_actor(self, case_id: str, actor_id: str, added_by: str) -> Case:
        case = self._get_required_case(case_id)
        if actor_id not in case.actor_ids:
            case.actor_ids.append(actor_id)
            case.updated_at = datetime.now(timezone.utc).isoformat()
        return case

    def add_link(self, case_id: str, link_id: str, added_by: str) -> Case:
        case = self._get_required_case(case_id)
        if link_id not in case.link_ids:
            case.link_ids.append(link_id)
            case.updated_at = datetime.now(timezone.utc).isoformat()
        return case

    def add_evidence(self, case_id: str, evidence_id: str, added_by: str) -> Case:
        case = self._get_required_case(case_id)
        if evidence_id not in case.evidence_ids:
            case.evidence_ids.append(evidence_id)
            case.updated_at = datetime.now(timezone.utc).isoformat()
        return case

    def add_note(self, case_id: str, author: str, text: str) -> Case:
        case = self._get_required_case(case_id)
        now = datetime.now(timezone.utc).isoformat()
        nid = f"note_{hashlib.sha256(f'{case_id}_{author}_{now}'.encode()).hexdigest()[:10]}"
        note = CaseNote(note_id=nid, author=author, text=text, timestamp=now)
        case.notes.append(note)
        case.updated_at = now
        return case

    def update_status(self, case_id: str, new_status: str, updated_by: str) -> Case:
        valid_statuses = ["open", "under_review", "closed", "archived"]
        if new_status not in valid_statuses:
            raise ValueError(f"Invalid status '{new_status}'. Allowed: {valid_statuses}")
        case = self._get_required_case(case_id)
        case.status = new_status
        case.updated_at = datetime.now(timezone.utc).isoformat()
        return case

    def set_legal_hold(self, case_id: str, hold_status: bool, updated_by: str) -> Case:
        case = self._get_required_case(case_id)
        case.legal_hold = hold_status
        case.updated_at = datetime.now(timezone.utc).isoformat()
        return case

    def list_cases(self, created_by: Optional[str] = None) -> List[Case]:
        if created_by:
            return [c for c in self._cases.values() if c.created_by == created_by]
        return list(self._cases.values())

    def _get_required_case(self, case_id: str) -> Case:
        case = self.get_case(case_id)
        if not case:
            raise ValueError(f"Case '{case_id}' not found.")
        return case
