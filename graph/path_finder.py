from typing import Dict, Any, Optional
from graph.base_graph import BaseGraphProjection
from graph.networkx_projection import NetworkXProjection

class PathFinder:
    """
    Multi-hop path analysis helper.
    Computes path confidence decay along chains, identifies bottleneck edges,
    and generates analyst explanations.
    """

    def __init__(self, projection: Optional[BaseGraphProjection] = None):
        self.projection = projection or NetworkXProjection()

    def find_attribution_paths(
        self,
        source_id: str,
        target_id: str,
        max_hops: int = 4,
        min_score: float = 0.0
    ) -> Dict[str, Any]:
        """
        Executes multi-hop path analysis between source_id and target_id.
        Returns ranked paths with bottleneck analysis.
        """
        paths = self.projection.find_paths(
            source_id=source_id,
            target_id=target_id,
            max_hops=max_hops,
            min_score=min_score
        )

        if not paths:
            return {
                "source_entity": source_id,
                "target_entity": target_id,
                "paths_found": 0,
                "paths": [],
                "highest_confidence": 0.0,
                "summary": f"No attribution paths found between {source_id} and {target_id} within {max_hops} hops."
            }

        top_path = paths[0]
        summary = (
            f"Found {len(paths)} attribution path(s) between {source_id} and {target_id}. "
            f"Top path has {top_path['hops']} hop(s) with aggregated confidence {top_path['path_confidence']:.2f}."
        )

        return {
            "source_entity": source_id,
            "target_entity": target_id,
            "paths_found": len(paths),
            "paths": paths,
            "highest_confidence": top_path["path_confidence"],
            "summary": summary
        }
