"""
Base Adapter Module for the SIH26151 Dark-Web Threat Actor Attribution Platform.
Defines the abstract contract for all local evidence adapters.
"""
from abc import ABC, abstractmethod
from typing import Any, List
from models.evidence import EvidenceUnit


class BaseAdapter(ABC):
    """
    Abstract Base Adapter defining the standard interface for all local evidence adapters.
    All local adapters must inherit from BaseAdapter and implement extract().
    """

    def supports(self, input_data: Any) -> bool:
        """
        Check if the adapter supports the given input payload.
        Default implementation returns True if input_data is a dictionary.
        Subclasses may override with specific validation logic.
        """
        return isinstance(input_data, dict)

    @abstractmethod
    def extract(self, input_data: dict) -> list[EvidenceUnit]:
        """
        Processes input data and emits a list of validated EvidenceUnit objects.

        Args:
            input_data: Dictionary containing module observations or raw match payloads.

        Returns:
            list[EvidenceUnit]: List of canonical, validated EvidenceUnit instances.
        """
        raise NotImplementedError("Subclasses must implement extract()")
