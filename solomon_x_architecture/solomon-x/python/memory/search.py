"""
Memory Search Module for Solomon X
Implements the refined MemoryOS search flow:
1. Hot tier (SQLite + FTS5) for instant keyword search
2. Warm tier (LanceDB) for GPU-accelerated vector search
3. Re-rank with lightweight cross-encoder (Phi-3-mini GGUF)

This is a simplified version showing the flow. In production:
- VSA-Lite hypervector binding would be used for query transformation
- Actual Phi-3-mini would be used for re-ranking
"""

import time
import numpy as np
from typing import List, Dict, Optional
from dataclasses import dataclass

# Import our memory store
from .store import MemoryStore

@dataclass
class SearchResult:
    id: str
    content: str
    timestamp: float
    salience: float
    novelty: float
    metadata: dict
    tier: str  # 'hot', 'warm', 'cold'
    score: float  # Combined relevance score

class MemorySearcher:
    def __init__(self, db_path: str = "./data/memory"):
        self.store = MemoryStore(db_path)
        # In production: would initialize VSA-Lite and LanceDB here
        # For MVP: we'll simulate the search flow with our store

    def search(self, query: str, limit: int = 10) -> List[SearchResult]:
        """
        Execute the full memory search pipeline
        Target latency: <10ms p99 on RTX 4060 laptop
        """
        start_time = time.perf_counter()

        # Step 1: Hot tier keyword search (L1) - target <1ms
        hot_results = self._search_hot_tier(query, limit * 2)

        # If we have enough high-salience results, return early
        high_salience_hot = [r for r in hot_results if r.salience > 0.7]
        if len(high_salience_hot) >= limit:
            elapsed = (time.perf_counter() - start_time) * 1000
            print(f"Hot tier search completed in {elapsed:.2f}ms")
            return high_salience_hot[:limit]

        # Step 2: Warm tier semantic search (L2) - target <5ms with GPU
        # In production: would use VSA-Lite to transform query to hypervector
        # then search LanceDB with IVF-PQ index (GPU-accelerated)
        warm_results = self._search_warm_tier(query, limit * 2,
                                              exclude_ids={r.id for r in hot_results})

        # Combine results
        all_results = hot_results + warm_results

        # Step 3: Re-rank with cross-encoder (Phi-3-mini) - target <3ms
        # In production: would use quantized Phi-3-mini to score relevance
        # For MVP: use simple salience/novelty combination
        ranked_results = self._rerank_results(all_results, query)

        elapsed = (time.perf_counter() - start_time) * 1000
        print(f"Full search completed in {elapsed:.2f}ms (target: <10ms)")

        return ranked_results[:limit]

    def _search_hot_tier(self, query: str, limit: int) -> List[SearchResult]:
        """Search L1 using SQLite FTS5"""
        # This would call the store's _search_hot_tier method
        # For demonstration, we'll return mock results
        mock_results = [
            SearchResult(
                id="hot_001",
                content="User solved Rust borrowing error by adding lifetime annotation",
                timestamp=time.time() - 3600,  # 1 hour ago
                salience=0.85,
                novelty=0.7,
                metadata={"domain": "rust", "tags": ["programming", "debugging"]},
                tier="hot",
                score=0.0  # Will be set in re-rank
            ),
            SearchResult(
                id="hot_002",
                content="Morning standup: discussed sprint planning for cognitive twin module",
                timestamp=time.time() - 7200,  # 2 hours ago
                salience=0.6,
                novelty=0.4,
                metadata={"domain": "meeting", "tags": ["planning", "team"]},
                tier="hot",
                score=0.0
            )
        ]
        return mock_results[:limit]

    def _search_warm_tier(self, query: str, limit: int, exclude_ids: set) -> List[SearchResult]:
        """Search L2 using LanceDB (GPU-accelerated)"""
        # In production:
        # 1. Transform query to hypervector using VSA-Lite
        # 2. Search LanceDB with IVF-PQ index
        # 3. Fetch corresponding content from hot tier
        mock_results = [
            SearchResult(
                id="warm_001",
                content="Rust ownership rules: values have a single owner at any time",
                timestamp=time.time() - 86400,  # 1 day ago
                salience=0.75,
                novelty=0.6,
                metadata={"domain": "rust", "tags": ["ownership", "basics"]},
                tier="warm",
                score=0.0
            ),
            SearchResult(
                id="warm_002",
                content="Cognitive load peaks during context switching between tasks",
                timestamp=time.time() - 43200,  # 12 hours ago
                salience=0.8,
                novelty=0.5,
                metadata={"domain": "psychology", "tags": ["cognitive", "productivity"]},
                tier="warm",
                score=0.0
            )
        ]
        # Filter out excluded IDs
        filtered = [r for r in mock_results if r.id not in exclude_ids]
        return filtered[:limit]

    def _rerank_results(self, results: List[SearchResult], query: str) -> List[SearchResult]:
        """Re-rank results using lightweight cross-encoder"""
        # In production:
        # 1. Load quantized Phi-3-mini GGUF model (once at startup)
        # 2. For each result, create [query, passage] pair
        # 3. Get relevance score from model
        # 4. Sort by score

        # For MVP: use simple heuristic based on salience and novelty
        for result in results:
            # Weighted combination: 60% salience, 40% novelty
            result.score = (result.salience * 0.6) + (result.novelty * 0.4)

            # Boost score for exact keyword matches (simplified)
            if query.lower() in result.content.lower():
                result.score = min(1.0, result.score + 0.2)

        # Sort by score descending
        results.sort(key=lambda x: x.score, reverse=True)
        return results

def demonstrate_search():
    """Demonstrate the memory search functionality"""
    print("=== Solomon X Memory Search Demo ===\n")

    searcher = MemorySearcher()

    # Test queries
    queries = [
        "Rust borrowing error",
        "cognitive load",
        "morning standup"
    ]

    for query in queries:
        print(f"Query: '{query}'")
        results = searcher.search(query, limit=3)

        print(f"Found {len(results)} results:")
        for i, result in enumerate(results, 1):
            print(f"  {i}. [{result.tier}] {result.content[:60]}...")
            print(f"     Salience: {result.salience:.2f}, Novelty: {result.novelty:.2f}, Score: {result.score:.2f}")
            print(f"     Tags: {result.metadata.get('tags', [])}")
        print()

if __name__ == "__main__":
    demonstrate_search()