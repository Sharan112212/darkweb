from abc import ABC, abstractmethod
from typing import List, Any
from models.evidence import EvidenceUnit

class BaseScanner(ABC):
    """
    Abstract Base Class for network and infrastructure scanners.
    All scanners must emit standardized EvidenceUnit objects.
    """

    @abstractmethod
    def scan(self, target: str, capture_id: str = "cap_scanner_init", **kwargs: Any) -> List[EvidenceUnit]:
        """
        Executes a scan against the target (URL or onion address).
        
        Args:
            target: The target onion address or URL.
            capture_id: Associated capture identifier.
            **kwargs: Optional execution overrides (e.g. fixture_path).
            
        Returns:
            List of EvidenceUnit records representing infrastructure evidence.
        """
