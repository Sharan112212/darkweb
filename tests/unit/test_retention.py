import pytest
from governance.retention import RetentionManager

def test_retention_manager_legal_hold_and_tombstone():
    rm = RetentionManager()

    # Enable legal hold
    rm.set_legal_hold("item_100", True, "reviewer_1")
    assert rm.is_under_legal_hold("item_100") is True

    # Attempt tombstoning item under legal hold -> must fail
    with pytest.raises(ValueError, match="Active Legal Hold"):
        rm.tombstone_item("item_100", reason="Expiry", requested_by="system")

    # Release legal hold
    rm.set_legal_hold("item_100", False, "reviewer_1")
    assert rm.is_under_legal_hold("item_100") is False

    # Tombstone item
    tombstone = rm.tombstone_item("item_100", reason="Retention policy 180 days", requested_by="system")
    assert tombstone["status"] == "tombstoned"
    assert rm.is_tombstoned("item_100") is True
    assert "tombstoned per retention policy" in tombstone["tombstone_notice"]
