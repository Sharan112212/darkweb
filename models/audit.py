from typing import List, Dict, Any
from pydantic import BaseModel, Field

class AuditEvent(BaseModel):
    event_id: str
    request_id: str
    user_id: str
    action: str
    object_id: str
    timestamp: str
    details: Dict[str, Any] = Field(default_factory=dict)

class TimelineEvent(BaseModel):
    event_id: str
    event_type: str
    entity_id: str
    timestamp: str
    time_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    description: str
    evidence_ids: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
