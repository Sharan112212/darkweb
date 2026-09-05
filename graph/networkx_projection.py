import networkx as nx
from typing import Dict, Any, List, Optional
from graph.base_graph import BaseGraphProjection
from db.repositories.link_repo import LinkRepository

class NetworkXProjection(BaseGraphProjection):
    """
    In-memory NetworkX graph projection engine.
    Supports graph sync, multi-hop path traversal, confidence calculation,
    and date-bounded sub-graph expansion with node truncation limits (EC-38).
    Does not require external Neo4j services during demo/offline deployment.
    """

    def __init__(self):
        self.graph = nx.Graph()

    def clear(self) -> None:
        """Clears the graph."""
        self.graph.clear()

    def add_node(self, entity_id: str, label: str = "Entity", attributes: Optional[Dict[str, Any]] = None) -> None:
        attrs = dict(attributes or {})
        attrs["id"] = entity_id
        attrs["label"] = label
        self.graph.add_node(entity_id, **attrs)

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        link_id: str,
        score: float,
        tier: str,
        attributes: Optional[Dict[str, Any]] = None
    ) -> None:
        if not self.graph.has_node(source_id):
            self.add_node(source_id)
        if not self.graph.has_node(target_id):
            self.add_node(target_id)

        edge_attrs = dict(attributes or {})
        edge_attrs["link_id"] = link_id
        edge_attrs["score"] = float(score)
        edge_attrs["tier"] = str(tier)
        # Cost metric for Dijkstra shortest path (higher score = lower cost)
        edge_attrs["weight"] = 1.0 - min(0.99, max(0.01, float(score)))

        self.graph.add_edge(source_id, target_id, **edge_attrs)

    def sync_from_db(self, db_path: Optional[str] = None, min_score: float = 0.0) -> int:
        """Loads candidate links and entities from database repository."""
        self.clear()
        repo = LinkRepository(db_path)
        links = repo.list_all()

        added_count = 0
        for link in links:
            score = float(link.get("score", 0.0))
            if score < min_score:
                continue

            state = link.get("state", "proposed")
            if state in ["rejected", "superseded"]:
                continue

            left_id = link["left_entity_id"]
            right_id = link["right_entity_id"]
            link_id = link["link_id"]
            tier = link.get("tier", "unresolved")

            self.add_edge(
                source_id=left_id,
                target_id=right_id,
                link_id=link_id,
                score=score,
                tier=tier,
                attributes={
                    "state": state,
                    "score_model_version": link.get("score_model_version", "scoring-v1.0"),
                    "explanation": link.get("explanation", ""),
                    "created_at": link.get("created_at", "")
                }
            )
            added_count += 1

        return added_count

    def get_projection(self) -> Dict[str, Any]:
        """Returns node and edge dictionary representation."""
        nodes_list = []
        for n, data in self.graph.nodes(data=True):
            node_dict = dict(data)
            node_dict["id"] = n
            nodes_list.append(node_dict)

        edges_list = []
        for u, v, data in self.graph.edges(data=True):
            edge_dict = dict(data)
            edge_dict["source"] = u
            edge_dict["target"] = v
            edges_list.append(edge_dict)

        return {
            "nodes": nodes_list,
            "edges": edges_list,
            "node_count": len(nodes_list),
            "edge_count": len(edges_list)
        }

    def get_subgraph(
        self,
        entity_id: str,
        depth: int = 2,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        min_score: float = 0.0,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        Returns k-hop ego subgraph centered at entity_id.
        Supports date filtering and truncation limits (EC-38).
        """
        if not self.graph.has_node(entity_id):
            return {
                "nodes": [],
                "edges": [],
                "node_count": 0,
                "edge_count": 0,
                "truncated": False,
                "absence_reason": "no_data_for_actor"
            }

        # Compute k-hop ego subgraph nodes
        ego_nodes = set(nx.single_source_shortest_path_length(self.graph, entity_id, cutoff=depth).keys())
        subg = self.graph.subgraph(ego_nodes).copy()

        # Filter edges by score and date range
        edges_to_remove = []
        for u, v, data in subg.edges(data=True):
            score = data.get("score", 0.0)
            created_at = data.get("created_at") or data.get("updated_at", "")

            if score < min_score:
                edges_to_remove.append((u, v))
                continue

            if date_from and created_at and created_at < date_from:
                edges_to_remove.append((u, v))
                continue

            if date_to and created_at and created_at > date_to:
                edges_to_remove.append((u, v))
                continue

        subg.remove_edges_from(edges_to_remove)
        # Remove isolated nodes except the root entity
        isolated = [n for n in subg.nodes() if subg.degree(n) == 0 and n != entity_id]
        subg.remove_nodes_from(isolated)

        all_nodes = list(subg.nodes(data=True))
        all_edges = list(subg.edges(data=True))

        truncated = len(all_nodes) > limit
        if truncated:
            # Truncate nodes list to limit
            truncated_nodes = all_nodes[:limit]
            valid_node_ids = set(n for n, _ in truncated_nodes)
            all_nodes = truncated_nodes
            all_edges = [(u, v, d) for u, v, d in all_edges if u in valid_node_ids and v in valid_node_ids]

        nodes_list = []
        for n, data in all_nodes:
            node_dict = dict(data)
            node_dict["id"] = n
            nodes_list.append(node_dict)

        edges_list = []
        for u, v, data in all_edges:
            edge_dict = dict(data)
            edge_dict["source"] = u
            edge_dict["target"] = v
            edges_list.append(edge_dict)

        return {
            "center_entity_id": entity_id,
            "depth": depth,
            "nodes": nodes_list,
            "edges": edges_list,
            "node_count": len(nodes_list),
            "edge_count": len(edges_list),
            "truncated": truncated
        }

    def find_paths(
        self,
        source_id: str,
        target_id: str,
        max_hops: int = 4,
        min_score: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        Finds all simple paths up to max_hops between source_id and target_id.
        Calculates aggregated path confidence score using path edge product.
        """
        if not self.graph.has_node(source_id) or not self.graph.has_node(target_id):
            return []

        paths_result = []
        try:
            raw_paths = list(nx.all_simple_paths(self.graph, source=source_id, target=target_id, cutoff=max_hops))
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return []

        for p_nodes in raw_paths:
            edge_scores = []
            edge_details = []
            valid_path = True

            for i in range(len(p_nodes) - 1):
                u = p_nodes[i]
                v = p_nodes[i + 1]
                edge_data = self.graph.get_edge_data(u, v)
                if not edge_data:
                    valid_path = False
                    break
                s = edge_data.get("score", 0.0)
                if s < min_score:
                    valid_path = False
                    break
                edge_scores.append(s)
                edge_details.append({
                    "from": u,
                    "to": v,
                    "link_id": edge_data.get("link_id"),
                    "score": s,
                    "tier": edge_data.get("tier")
                })

            if not valid_path or not edge_scores:
                continue

            path_confidence = 1.0
            for s in edge_scores:
                path_confidence *= s
            path_confidence = round(path_confidence, 4)

            explanation = (
                f"Multi-hop attribution path ({len(edge_scores)} hops): "
                + " -> ".join(p_nodes)
                + f" (Aggregated Confidence: {path_confidence:.2f})"
            )

            paths_result.append({
                "hops": len(edge_scores),
                "nodes": p_nodes,
                "edges": edge_details,
                "path_confidence": path_confidence,
                "explanation": explanation
            })

        paths_result.sort(key=lambda x: x["path_confidence"], reverse=True)
        return paths_result
