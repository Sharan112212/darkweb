import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from db.repositories.entity_repo import EntityRepository
from db.repositories.link_repo import LinkRepository
from db.repositories.evidence_repo import EvidenceRepository
from graph.base_graph import BaseGraphProjection
from graph.neo4j_projection import Neo4jProjection
from graph.networkx_projection import NetworkXProjection

logger = logging.getLogger(__name__)

class GraphReconciliationEngine:
    """
    Graph Reconciliation and Migration Engine (EC-32).
    PostgreSQL / canonical database remains the single source of truth.
    Neo4j / NetworkX projections are rebuilt from canonical records.
    Provides backfill, reconciliation validation, and safe rollback capabilities.
    """

    def __init__(self, db_path: Optional[str] = None, graph_projection: Optional[BaseGraphProjection] = None):
        self.db_path = db_path
        self.graph = graph_projection or Neo4jProjection()

    def backfill(self, min_score: float = 0.0) -> Dict[str, Any]:
        """
        Backfills canonical entities and candidate links from database into graph projection.
        Returns count of synced nodes and edges.
        """
        entity_repo = EntityRepository(self.db_path)
        link_repo = LinkRepository(self.db_path)

        entities = entity_repo.list_all()
        links = link_repo.list_all()

        nodes_synced = 0
        edges_synced = 0

        # Sync entities as graph nodes
        for ent in entities:
            eid = ent.get("entity_id")
            etype = ent.get("entity_type", "Entity")
            if eid:
                self.graph.add_node(eid, label=etype, attributes=ent)
                nodes_synced += 1

        # Sync candidate links as graph edges
        for link in links:
            score = float(link.get("score", 0.0))
            if score < min_score:
                continue
            state = link.get("state", "proposed")
            if state in ["rejected", "superseded"]:
                continue

            left_id = link.get("left_entity_id")
            right_id = link.get("right_entity_id")
            link_id = link.get("link_id")
            tier = link.get("tier", "unresolved")

            if left_id and right_id and link_id:
                self.graph.add_edge(
                    source_id=left_id,
                    target_id=right_id,
                    link_id=link_id,
                    score=score,
                    tier=tier,
                    attributes=link
                )
                edges_synced += 1

        return {
            "status": "completed",
            "nodes_synced": nodes_synced,
            "edges_synced": edges_synced,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    def reconcile(self) -> Dict[str, Any]:
        """
        Reconciles canonical database against graph projection.
        Compares entity count and link count. Reports missing IDs if any (EC-32).
        """
        entity_repo = EntityRepository(self.db_path)
        link_repo = LinkRepository(self.db_path)

        canonical_entities = {e["entity_id"]: e for e in entity_repo.list_all() if "entity_id" in e}
        canonical_links = {l["link_id"]: l for l in link_repo.list_all() if l.get("state") not in ["rejected", "superseded"]}

        projection = self.graph.get_projection()
        graph_nodes = {n["id"]: n for n in projection.get("nodes", []) if "id" in n}
        graph_edges = {e["link_id"]: e for e in projection.get("edges", []) if "link_id" in e}

        missing_entities = [eid for eid in canonical_entities if eid not in graph_nodes]
        missing_links = [lid for lid in canonical_links if lid not in graph_edges]

        is_reconciled = (len(missing_entities) == 0) and (len(missing_links) == 0)

        return {
            "reconciled": is_reconciled,
            "canonical": {
                "entities_count": len(canonical_entities),
                "links_count": len(canonical_links)
            },
            "graph": {
                "nodes_count": len(graph_nodes),
                "edges_count": len(graph_edges)
            },
            "missing_entities_count": len(missing_entities),
            "missing_links_count": len(missing_links),
            "missing_entities": missing_entities[:50],  # preview top 50
            "missing_links": missing_links[:50],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    def rollback(self) -> Dict[str, Any]:
        """
        Rollback procedure: clears graph projection and rebuilds clean state from canonical database.
        Ensures zero data loss during graph server recovery or migration rollback (EC-32).
        """
        logger.info("Executing graph projection rollback and resynchronization...")
        
        # Clear graph projection
        if hasattr(self.graph, "nx_fallback"):
            self.graph.nx_fallback.clear()

        # Re-run backfill from canonical DB
        backfill_result = self.backfill()
        reconciliation_result = self.reconcile()

        return {
            "status": "rolled_back_and_resynced",
            "backfill": backfill_result,
            "reconciliation": reconciliation_result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
