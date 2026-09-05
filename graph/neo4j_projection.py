import os
import logging
from typing import Dict, Any, List, Optional
from graph.base_graph import BaseGraphProjection
from graph.networkx_projection import NetworkXProjection

logger = logging.getLogger(__name__)

class Neo4jProjection(BaseGraphProjection):
    """
    Neo4j graph database projection engine wrapper.
    Falls back gracefully to NetworkX in-memory projection if Neo4j is offline or unavailable.
    """

    def __init__(
        self,
        uri: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None
    ):
        self.uri = uri or os.environ.get("NEO4J_URI", "bolt://localhost:7687")
        self.user = user or os.environ.get("NEO4J_USER", "neo4j")
        self.password = password or os.environ.get("NEO4J_PASSWORD", "changeme_in_production")
        
        self.driver = None
        self.nx_fallback = NetworkXProjection()
        self._connected = False

        self._connect()

    def _connect(self) -> bool:
        """Attempts connection to Neo4j server."""
        try:
            import neo4j
            self.driver = neo4j.GraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password),
                connection_timeout=3.0
            )
            # Verify connectivity
            self.driver.verify_connectivity()
            self._connected = True
            logger.info(f"Connected to Neo4j graph database at {self.uri}")
            return True
        except Exception as e:
            logger.warning(f"Neo4j database unavailable at {self.uri} ({e}). Using NetworkX fallback (EC-07).")
            self._connected = False
            self.driver = None
            return False

    @property
    def is_connected(self) -> bool:
        return self._connected

    def add_node(self, entity_id: str, label: str = "Entity", attributes: Optional[Dict[str, Any]] = None) -> None:
        self.nx_fallback.add_node(entity_id, label=label, attributes=attributes)
        if not self._connected or not self.driver:
            return

        cypher = f"MERGE (n:{label} {{id: $entity_id}}) SET n += $attributes"
        try:
            with self.driver.session() as session:
                session.run(cypher, entity_id=entity_id, attributes=attributes or {})
        except Exception as e:
            logger.warning(f"Neo4j add_node failed: {e}")

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        link_id: str,
        score: float,
        tier: str,
        attributes: Optional[Dict[str, Any]] = None
    ) -> None:
        self.nx_fallback.add_edge(source_id, target_id, link_id=link_id, score=score, tier=tier, attributes=attributes)
        if not self._connected or not self.driver:
            return

        cypher = """
        MERGE (a:Entity {id: $source_id})
        MERGE (b:Entity {id: $target_id})
        MERGE (a)-[r:ASSOCIATED_WITH {link_id: $link_id}]->(b)
        SET r.score = $score, r.tier = $tier, r += $attributes
        """
        edge_attrs = dict(attributes or {})
        try:
            with self.driver.session() as session:
                session.run(
                    cypher,
                    source_id=source_id,
                    target_id=target_id,
                    link_id=link_id,
                    score=float(score),
                    tier=str(tier),
                    attributes=edge_attrs
                )
        except Exception as e:
            logger.warning(f"Neo4j add_edge failed: {e}")

    def sync_from_db(self, db_path: Optional[str] = None, min_score: float = 0.0) -> int:
        count = self.nx_fallback.sync_from_db(db_path=db_path, min_score=min_score)
        if not self._connected or not self.driver:
            return count

        # If Neo4j connected, sync nodes & relationships to Neo4j
        proj = self.nx_fallback.get_projection()
        for node in proj["nodes"]:
            self.add_node(node["id"], label=node.get("label", "Entity"), attributes=node)
        for edge in proj["edges"]:
            self.add_edge(
                source_id=edge["source"],
                target_id=edge["target"],
                link_id=edge["link_id"],
                score=edge["score"],
                tier=edge["tier"],
                attributes=edge
            )
        return count

    def get_projection(self) -> Dict[str, Any]:
        if not self._connected or not self.driver:
            return self.nx_fallback.get_projection()

        cypher_nodes = "MATCH (n:Entity) RETURN n.id AS id, labels(n)[0] AS label, properties(n) AS props"
        cypher_edges = "MATCH (a:Entity)-[r:ASSOCIATED_WITH]->(b:Entity) RETURN a.id AS source, b.id AS target, properties(r) AS props"

        try:
            nodes_list = []
            edges_list = []
            with self.driver.session() as session:
                n_res = session.run(cypher_nodes)
                for rec in n_res:
                    props = dict(rec["props"] or {})
                    props["id"] = rec["id"]
                    props["label"] = rec["label"]
                    nodes_list.append(props)

                e_res = session.run(cypher_edges)
                for rec in e_res:
                    props = dict(rec["props"] or {})
                    props["source"] = rec["source"]
                    props["target"] = rec["target"]
                    edges_list.append(props)

            return {
                "nodes": nodes_list,
                "edges": edges_list,
                "node_count": len(nodes_list),
                "edge_count": len(edges_list),
                "engine": "neo4j"
            }
        except Exception as e:
            logger.warning(f"Neo4j get_projection query failed: {e}. Returning NetworkX projection.")
            return self.nx_fallback.get_projection()

    def find_paths(
        self,
        source_id: str,
        target_id: str,
        max_hops: int = 4,
        min_score: float = 0.0
    ) -> List[Dict[str, Any]]:
        # If Neo4j is offline or unavailable, delegate to NetworkX
        if not self._connected or not self.driver:
            return self.nx_fallback.find_paths(source_id, target_id, max_hops=max_hops, min_score=min_score)

        cypher = f"""
        MATCH path = (a:Entity {{id: $source_id}})-[r:ASSOCIATED_WITH*1..{max_hops}]-(b:Entity {{id: $target_id}})
        RETURN path
        """
        try:
            paths_result = []
            with self.driver.session() as session:
                res = session.run(cypher, source_id=source_id, target_id=target_id)
                for rec in res:
                    p = rec["path"]
                    p_nodes = [node["id"] for node in p.nodes]
                    edge_scores = [rel["score"] for rel in p.relationships if "score" in rel]
                    
                    if any(s < min_score for s in edge_scores):
                        continue

                    path_conf = 1.0
                    for s in edge_scores:
                        path_conf *= s
                    path_conf = round(path_conf, 4)

                    paths_result.append({
                        "hops": len(p.relationships),
                        "nodes": p_nodes,
                        "path_confidence": path_conf,
                        "explanation": f"Neo4j Multi-hop path ({len(p.relationships)} hops): {' -> '.join(p_nodes)}"
                    })
            paths_result.sort(key=lambda x: x["path_confidence"], reverse=True)
            return paths_result
        except Exception as e:
            logger.warning(f"Neo4j find_paths failed: {e}. Falling back to NetworkX.")
            return self.nx_fallback.find_paths(source_id, target_id, max_hops=max_hops, min_score=min_score)

    def close(self) -> None:
        if self.driver:
            try:
                self.driver.close()
            except Exception:
                pass
