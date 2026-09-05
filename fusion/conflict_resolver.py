"""
ConflictResolver Module.
Identifies competing candidate link hypotheses across entity pairs
and assigns deterministic conflict_set_id and competing_link_ids.
"""

import hashlib
from collections import defaultdict, deque
from typing import Any, Dict, List, Set, Union
from models.candidate_link import CandidateLink


class ConflictResolver:
    """
    Identifies competing candidate link hypotheses (e.g. Actor A linked to Actor B with Key 1,
    and Actor A linked to Actor C with Key 2) and assigns deterministic conflict_set_id
    and sets competing_link_ids.
    """

    @classmethod
    def resolve_conflicts(
        cls, candidate_links: List[Union[CandidateLink, Dict[str, Any]]]
    ) -> List[Union[CandidateLink, Dict[str, Any]]]:
        """
        Processes candidate links, detects competing hypotheses where an entity is linked
        to multiple distinct partner entities, and assigns deterministic conflict_set_id
        and competing_link_ids.

        Returns:
            Updated candidate links with conflict metadata populated.
        """
        if not candidate_links:
            return []

        # 1. Build entity -> list of links map
        entity_to_links: Dict[str, List[Union[CandidateLink, Dict[str, Any]]]] = defaultdict(list)
        for link in candidate_links:
            left = getattr(link, "left_entity_id", None) or (link.get("left_entity_id") if isinstance(link, dict) else "")
            right = getattr(link, "right_entity_id", None) or (link.get("right_entity_id") if isinstance(link, dict) else "")
            if left:
                entity_to_links[left].append(link)
            if right:
                entity_to_links[right].append(link)

        # 2. Build adjacency graph between competing candidate links
        # Two links compete if they share at least one entity
        link_id_map: Dict[str, Union[CandidateLink, Dict[str, Any]]] = {}
        adjacency: Dict[str, Set[str]] = defaultdict(set)

        for link in candidate_links:
            lid = getattr(link, "link_id", None) or (link.get("link_id") if isinstance(link, dict) else "")
            link_id_map[lid] = link

            left = getattr(link, "left_entity_id", None) or (link.get("left_entity_id") if isinstance(link, dict) else "")
            right = getattr(link, "right_entity_id", None) or (link.get("right_entity_id") if isinstance(link, dict) else "")

            # Competing links through left entity
            for other in entity_to_links.get(left, []):
                other_id = getattr(other, "link_id", None) or (other.get("link_id") if isinstance(other, dict) else "")
                if other_id and other_id != lid:
                    adjacency[lid].add(other_id)
                    adjacency[other_id].add(lid)

            # Competing links through right entity
            for other in entity_to_links.get(right, []):
                other_id = getattr(other, "link_id", None) or (other.get("link_id") if isinstance(other, dict) else "")
                if other_id and other_id != lid:
                    adjacency[lid].add(other_id)
                    adjacency[other_id].add(lid)

        # 3. Find connected components of competing links
        visited: Set[str] = set()
        conflict_groups: List[List[str]] = []

        for lid in link_id_map:
            if lid not in visited:
                component = []
                queue = deque([lid])
                visited.add(lid)

                while queue:
                    curr = queue.popleft()
                    component.append(curr)
                    for neighbor in adjacency.get(curr, set()):
                        if neighbor not in visited:
                            visited.add(neighbor)
                            queue.append(neighbor)

                if len(component) > 1:
                    conflict_groups.append(sorted(component))
                else:
                    # Single link without conflicts
                    cls._set_conflict_attrs(link_id_map[lid], conflict_set_id=None, competing_ids=[])

        # 4. Assign deterministic conflict_set_id and competing_link_ids
        for group in conflict_groups:
            # Deterministic conflict_set_id derived from sorted member link IDs
            group_key = ",".join(group)
            digest = hashlib.sha256(group_key.encode("utf-8")).hexdigest()[:12]
            conflict_set_id = f"conf_{digest}"

            for lid in group:
                target_link = link_id_map[lid]
                competing_ids = [comp_id for comp_id in group if comp_id != lid]
                cls._set_conflict_attrs(target_link, conflict_set_id=conflict_set_id, competing_ids=competing_ids)

        return candidate_links

    @classmethod
    def identify_conflicts(
        cls, candidate_links: List[Union[CandidateLink, Dict[str, Any]]]
    ) -> Dict[str, List[Union[CandidateLink, Dict[str, Any]]]]:
        """
        Resolves conflicts and returns a dictionary mapping conflict_set_id to member links.
        """
        resolved = cls.resolve_conflicts(candidate_links)
        grouped: Dict[str, List[Union[CandidateLink, Dict[str, Any]]]] = defaultdict(list)
        for link in resolved:
            csid = getattr(link, "conflict_set_id", None) or (link.get("conflict_set_id") if isinstance(link, dict) else None)
            if csid:
                grouped[csid].append(link)
        return dict(grouped)

    @staticmethod
    def _set_conflict_attrs(
        link: Union[CandidateLink, Dict[str, Any]],
        conflict_set_id: Union[str, None],
        competing_ids: List[str],
    ) -> None:
        """Helper to set conflict_set_id and competing_link_ids on an object or dict."""
        if isinstance(link, dict):
            link["conflict_set_id"] = conflict_set_id
            link["competing_link_ids"] = competing_ids
        else:
            setattr(link, "conflict_set_id", conflict_set_id)
            setattr(link, "competing_link_ids", competing_ids)
