from datetime import datetime, timezone
from typing import Dict, Any, Optional

class RetentionManager:
    """
    Data Retention, Legal Hold, and Tombstone Engine (EC-05, EC-36).
    Applies retention policies, blocks deletion under Legal Hold,
    and tombstones deleted evidence without erasing audit trails.
    """

    def __init__(self):
        self._legal_holds: Dict[str, bool] = {}
        self._tombstones: Dict[str, Dict[str, Any]] = {}

    def set_legal_hold(self, item_id: str, hold_active: bool, set_by: str) -> Dict[str, Any]:
        self._legal_holds[item_id] = hold_active
        return {
            "item_id": item_id,
            "legal_hold": hold_active,
            "set_by": set_by,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    def is_under_legal_hold(self, item_id: str) -> bool:
        return self._legal_holds.get(item_id, False)

    def tombstone_item(self, item_id: str, reason: str, requested_by: str) -> Dict[str, Any]:
        """
        Tombstones an item (replaces content with tombstone notice) (EC-36).
        Blocks tombstoning if item is under Legal Hold.
        Preserves original ID and audit history.
        """
        if self.is_under_legal_hold(item_id):
            raise ValueError(f"Cannot tombstone item '{item_id}': Active Legal Hold is in effect.")

        now = datetime.now(timezone.utc).isoformat()
        tombstone_record = {
            "item_id": item_id,
            "status": "tombstoned",
            "tombstoned_at": now,
            "tombstoned_by": requested_by,
            "reason": reason,
            "tombstone_notice": f"Item '{item_id}' has been tombstoned per retention policy / takedown request. Audit trail preserved."
        }
        self._tombstones[item_id] = tombstone_record
        return tombstone_record

    def get_tombstone(self, item_id: str) -> Optional[Dict[str, Any]]:
        return self._tombstones.get(item_id)

    def is_tombstoned(self, item_id: str) -> bool:
        return item_id in self._tombstones
