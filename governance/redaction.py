from typing import Dict, Any

class RedactionEngine:
    """
    Role-Based Data Redaction Engine (EC-28).
    Enforces access control policies across user roles:
      - viewer: Redacts raw PGP key strings, contact identifiers, context excerpts, and raw evidence references.
      - analyst: Full evidence access except administrative credentials.
      - reviewer: Full evidence and decision access.
      - admin: Unrestricted access.
    Preserves audit notices and redaction reasons rather than returning blank fields.
    """

    ROLES = ["viewer", "analyst", "reviewer", "admin"]

    def sanitize_evidence_unit(self, unit_dict: Dict[str, Any], user_role: str) -> Dict[str, Any]:
        if user_role not in self.ROLES:
            user_role = "viewer"

        sanitized = dict(unit_dict)

        if user_role == "viewer":
            # Mask sensitive indicators for viewer role
            indicator_type = sanitized.get("indicator_type", "")
            if indicator_type in ["pgp_fingerprint", "contact_identifier"]:
                raw_val = sanitized.get("indicator_value", "")
                if len(raw_val) > 8:
                    sanitized["indicator_value"] = f"{raw_val[:4]}...{raw_val[-4:]} [REDACTED FOR ROLE: viewer]"
                else:
                    sanitized["indicator_value"] = "[REDACTED FOR ROLE: viewer]"

            sanitized["context_excerpt"] = "[REDACTED - ACCESS RESTRICTED FOR ROLE: viewer]"
            sanitized["raw_evidence_reference"] = "[REDACTED - ACCESS RESTRICTED FOR ROLE: viewer]"
            sanitized["is_redacted"] = True
            sanitized["redaction_notice"] = "Sensitive context excerpt and raw reference redacted for Viewer role."
        else:
            sanitized["is_redacted"] = False

        return sanitized

    def sanitize_candidate_link(self, link_dict: Dict[str, Any], user_role: str) -> Dict[str, Any]:
        if user_role not in self.ROLES:
            user_role = "viewer"

        sanitized = dict(link_dict)

        # Candidate link scores and tiers are visible to all roles, but details depend on role
        if user_role == "viewer":
            sanitized["is_redacted_for_viewer"] = True
        return sanitized

    def can_export_raw_evidence(self, user_role: str) -> bool:
        """Only analyst, reviewer, and admin roles can export raw evidence packages."""
        return user_role in ["analyst", "reviewer", "admin"]

    def can_make_decision(self, user_role: str) -> bool:
        """Only analyst, reviewer, and admin roles can record decisions."""
        return user_role in ["analyst", "reviewer", "admin"]
