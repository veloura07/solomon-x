import hashlib
import numpy as np
from typing import List, Protocol

class Embedder(Protocol):
    """
    Protocol defining the interface for Solomon X memory vector embedders.
    """
    def embed_query(self, text: str) -> List[float]:
        """Generate a vector representation of the query string."""
        ...

    @property
    def dimension(self) -> int:
        """Returns the output vector dimensionality."""
        ...

class HashingEmbedder:
    """
    VSA-Lite deterministic hashing hypervector embedder.
    Generates identical unit-norm hypervectors for identical texts across processes.
    Useful for local zero-cost deployments.
    """
    def __init__(self, dimension: int = 1024) -> None:
        self._dimension = dimension

    def embed_query(self, text: str) -> List[float]:
        # Perform SHA-256 hash to seed the pseudo-random generator deterministically
        hasher = hashlib.sha256(text.encode("utf-8"))
        seed = int(hasher.hexdigest()[:8], 16)
        rng = np.random.default_rng(seed)
        
        vec = rng.normal(0.0, 1.0, self._dimension)
        
        # Normalize to unit length (L2 norm) for clean cosine search operations
        norm = np.linalg.norm(vec)
        if norm > 0.0:
            vec = vec / norm
            
        return vec.tolist()

    @property
    def dimension(self) -> int:
        return self._dimension

class RandomEmbedder:
    """
    Random vector placeholder for debugging or initialization tests.
    Non-deterministic across calls.
    """
    def __init__(self, dimension: int = 1024) -> None:
        self._dimension = dimension

    def embed_query(self, text: str) -> List[float]:
        vec = np.random.normal(0.0, 1.0, self._dimension)
        norm = np.linalg.norm(vec)
        if norm > 0.0:
            vec = vec / norm
        return vec.tolist()

    @property
    def dimension(self) -> int:
        return self._dimension
