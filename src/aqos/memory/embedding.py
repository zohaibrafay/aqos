"""
Embedding engine.

Provides lightweight deterministic embeddings for memory records.

This Sprint 007 implementation does not use external ML models yet.
It creates stable hash-based vectors so the memory subsystem can be
tested before real embedding models are integrated.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from math import sqrt


@dataclass(slots=True)
class EmbeddingEngine:
    """
    Deterministic embedding generator.
    """

    dimensions: int = 16

    def __post_init__(self) -> None:
        """
        Validate embedding configuration.
        """

        if self.dimensions <= 0:
            raise ValueError(
                "Embedding dimensions must be greater than zero."
            )

    def encode(
        self,
        text: str,
    ) -> list[float]:
        """
        Encode text into a deterministic numeric vector.
        """

        if not text:
            raise ValueError("Text cannot be empty.")

        raw_values = self._raw_values(text)
        magnitude = sqrt(sum(value * value for value in raw_values))

        if magnitude == 0:
            return raw_values

        return [
            value / magnitude
            for value in raw_values
        ]

    def encode_many(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        """
        Encode multiple text values.
        """

        if not texts:
            raise ValueError("Texts cannot be empty.")

        return [
            self.encode(text)
            for text in texts
        ]

    def _raw_values(
        self,
        text: str,
    ) -> list[float]:
        """
        Convert text into raw deterministic vector values.
        """

        values: list[float] = []
        counter = 0

        while len(values) < self.dimensions:
            digest = sha256(
                f"{counter}:{text}".encode("utf-8")
            ).digest()

            values.extend(
                byte / 255.0
                for byte in digest
            )

            counter += 1

        return values[: self.dimensions]


__all__ = ["EmbeddingEngine"]