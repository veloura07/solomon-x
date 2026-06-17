import os
import logging
import lancedb
import pyarrow as pa
from typing import Dict, Any, List, Optional

logger = logging.getLogger("solomon.memory.warm")

class LanceDBStore:
    """
    Warm vector store for high-dimensional episodic memories.
    Uses LanceDB for GPU-accelerated / CPU-optimized vector similarity searches.
    """
    def __init__(self, db_dir: str = "./data/lancedb", vector_dim: int = 1024) -> None:
        self.db_dir: str = db_dir
        self.vector_dim: int = vector_dim
        self.connected: bool = False
        self.db = None
        self.table = None
        self._initialize_vector_db()

    def _initialize_vector_db(self) -> None:
        """Initializes the database connection, schema, and creates the table."""
        logger.info(f"Initializing Warm Episodic Store under: {self.db_dir}")
        
        # Resolve path
        target_dir = self.db_dir
        if not os.path.isabs(target_dir):
            target_dir = os.path.join(os.getcwd(), "data", "lancedb")

        os.makedirs(target_dir, exist_ok=True)
        try:
            self.db = lancedb.connect(target_dir)
            
            # Create schema matching 1024D hypervectors
            schema = pa.schema([
                pa.field("id", pa.string()),
                pa.field("vector", pa.list_(pa.float32(), self.vector_dim)),
                pa.field("metadata", pa.string()),  # JSON string
                pa.field("timestamp", pa.float64()),
                pa.field("salience", pa.float32()),
                pa.field("novelty", pa.float32())
            ])
            
            try:
                self.table = self.db.open_table("memories")
            except Exception:
                self.table = self.db.create_table("memories", schema=schema)
                
            self.connected = True
            logger.info("LanceDB connection established and 'memories' table initialized.")
        except Exception as e:
            logger.error(f"Failed to initialize LanceDB connection: {e}")
            self.connected = False

    def insert_episodic_vector(
        self,
        memory_id: str,
        vector: List[float],
        metadata: Dict[str, Any],
        timestamp: float,
        salience: float,
        novelty: float
    ) -> None:
        """Inserts an embedding vector alongside its corresponding episodic metadata."""
        if not self.connected:
            raise ConnectionError("LanceDB warm store not initialized.")
            
        # Ensure vector size matches
        if len(vector) != self.vector_dim:
            vector = (vector + [0.0] * self.vector_dim)[:self.vector_dim]
            
        import json
        self.table.add([
            {
                "id": memory_id,
                "vector": vector,
                "metadata": json.dumps(metadata),
                "timestamp": timestamp,
                "salience": salience,
                "novelty": novelty
            }
        ])
        logger.debug(f"Inserted memory vector {memory_id} into warm store.")

    def query_similarity(
        self,
        query_vector: List[float],
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Executes a nearest-neighbor vector search query.
        Returns a sorted list of matching metadata frames.
        """
        if not self.connected:
            logger.warning("Query similarity called but LanceDB is not connected.")
            return []
            
        # Ensure vector size matches
        if len(query_vector) != self.vector_dim:
            query_vector = (query_vector + [0.0] * self.vector_dim)[:self.vector_dim]
            
        try:
            search_query = self.table.search(query_vector).metric("cosine").limit(limit)
            results = search_query.to_list()
            
            formatted_results = []
            import json
            for r in results:
                formatted_results.append({
                    "id": r["id"],
                    "timestamp": r["timestamp"],
                    "salience": r["salience"],
                    "novelty": r["novelty"],
                    "metadata": json.loads(r["metadata"]) if r["metadata"] else {},
                    "score": 1.0 - r.get("_distance", 0.0), # Cosine similarity score
                    "horizon": "L2"
                })
            return formatted_results
        except Exception as e:
            logger.error(f"Error querying similarity in LanceDB warm store: {e}")
            return []
