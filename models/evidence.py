from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator

class EvidenceUnit(BaseModel):
    evidence_id: str
    schema_version: str = "1.0.0"
    category: str = "K"
    capture_id: str
    source: str
    source_version: str
    indicator_type: str
    indicator_value: str
    indicator_role: Optional[str] = None
    linked_entities: List[str]
    confidence_weight: float = Field(..., ge=0.0, le=1.0)
    source_reliability: float = Field(default=1.0, ge=0.0, le=1.0)
    extraction_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source_claimed_time: Optional[str] = None
    observation_date: Optional[str] = None
    captured_at: str
    time_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source_url: str
    raw_evidence_hash: str
    raw_evidence_reference: str
    independence_group_id: str
    collector_mode: str = "fixture_replay"
    processing_status: str = "valid"
    explanation: str
    limitations: List[str] = Field(default_factory=list)
    context_excerpt: Optional[str] = None
    model_metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("linked_entities")
    @classmethod
    def validate_linked_entities(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("linked_entities must contain at least one entity ID")
        return v

    def validate_for_candidate_link(self) -> bool:
        """Validates that linked_entities contains exactly 2 entity IDs when used for candidate linking."""
        if len(self.linked_entities) != 2:
            raise ValueError(
                f"Candidate link requires exactly 2 linked entities, got {len(self.linked_entities)}"
            )
        return True
