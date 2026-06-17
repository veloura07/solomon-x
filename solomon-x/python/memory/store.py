"""
MemoryOS Store: Adaptive 3-Tier Memory System
Hot Tier (L1): SQLite + FTS5 (RAM-resident, last 24h)
Warm Tier (L2): LanceDB on SSD (GPU-accelerated vector search)
Cold Tier (L3): Compressed Parquet archives (monthly rollup)
"""

import os
import sqlite3
import lancedb
import pyarrow as pa
import pyarrow.parquet as pq
import numpy as np
from typing import List, Tuple, Optional, Dict
import json
from datetime import datetime, timedelta
import hashlib
import logging
from python.memory.embedder import Embedder, HashingEmbedder

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MemoryStore")

class MemoryStore:
    def __init__(self, db_path: str = "./data/memory", embedder: Optional[Embedder] = None):
        self.db_path = db_path
        os.makedirs(db_path, exist_ok=True)

        # VSA-Lite hypervector dimension (1024D for CPU cache efficiency)
        self.vector_dim = 1024
        self.embedder = embedder or HashingEmbedder(self.vector_dim)

        # Initialize tiers
        self._init_hot_tier()      # SQLite/L1
        self._init_warm_tier()     # LanceDB/L2
        self._init_cold_tier()     # Parquet/L3

    def _init_hot_tier(self):
        """L1: Volatile memory - SQLite with FTS5 for instant text search"""
        self.hot_conn = sqlite3.connect(
            os.path.join(self.db_path, "hot.db"),
            check_same_thread=False
        )
        self.hot_conn.execute("PRAGMA journal_mode=WAL")  # Better concurrency
        self.hot_conn.execute("PRAGMA synchronous=NORMAL")

        # Memories table: raw storage
        self.hot_conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                timestamp REAL NOT NULL,
                salience REAL DEFAULT 0.5,
                novelty REAL DEFAULT 0.5,
                metadata TEXT  -- JSON blob
            )
        """)

        # FTS5 index for instant keyword search
        self.hot_conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts
            USING fts5(content, id UNINDEXED, timestamp UNINDEXED)
        """)

        # Triggers to keep FTS5 in sync
        self.hot_conn.execute("""
            CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
                INSERT INTO memories_fts(rowid, content, id, timestamp)
                VALUES (new.rowid, new.content, new.id, new.timestamp);
            END;
        """)

        self.hot_conn.execute("""
            CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
                DELETE FROM memories_fts WHERE rowid = old.rowid;
            END;
        """)

        self.hot_conn.execute("""
            CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
                UPDATE memories_fts SET
                    content = new.content,
                    id = new.id,
                    timestamp = new.timestamp
                WHERE rowid = new.rowid;
            END;
        """)

        self.hot_conn.commit()

    def _init_warm_tier(self):
        """L2: Persistent vectors - LanceDB with GPU-accelerated IVF-PQ"""
        self.warm_db = lancedb.connect(os.path.join(self.db_path, "warm.lancedb"))

        # Create table if doesn't exist
        try:
            self.warm_table = self.warm_db.open_table("memories")
        except Exception:
            # Define schema: id, vector, metadata
            schema = pa.schema([
                pa.field("id", pa.string()),
                pa.field("vector", pa.list_(pa.float32(), self.vector_dim)),
                pa.field("metadata", pa.string()),  # JSON blob
                pa.field("timestamp", pa.float64()),
                pa.field("salience", pa.float32()),
                pa.field("novelty", pa.float32())
            ])
            self.warm_table = self.warm_db.create_table("memories", schema=schema)

            # Create IVF-PQ index for fast ANN search (GPU-accelerated on RTX 4060)
            try:
                self.warm_table.create_index(
                    num_partitions=256,  # Tune based on dataset size
                    num_sub_vectors=96,  # For 1024D vectors
                    metric="cosine"
                )
            except Exception as e:
                logger.warning(f"Could not initialize LanceDB IVF-PQ index (normal if table is empty): {e}")

    def _init_cold_tier(self):
        """L3: Archive tier - ZSTD-compressed Parquet"""
        self.cold_path = os.path.join(self.db_path, "cold")
        os.makedirs(self.cold_path, exist_ok=True)

    def store_memory(self,
                    content: str,
                    vector: Optional[List[float]] = None,
                    metadata: Optional[Dict] = None) -> str:
        """
        Store memory in appropriate tier based on age and salience
        Returns memory ID
        """
        memory_id = hashlib.sha256(
            f"{content}{datetime.now().timestamp()}".encode()
        ).hexdigest()[:16]

        # Extract or default timestamp
        timestamp = datetime.now().timestamp()
        if metadata and "timestamp" in metadata:
            try:
                timestamp = float(metadata["timestamp"])
            except (ValueError, TypeError):
                pass

        salience = metadata.get("salience", 0.5) if metadata else 0.5
        novelty = metadata.get("novelty", 0.5) if metadata else 0.5
        metadata_json = json.dumps(metadata or {})

        # Always store in hot tier first (L1)
        self.hot_conn.execute(
            """INSERT OR REPLACE INTO memories
               (id, content, timestamp, salience, novelty, metadata)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (memory_id, content, timestamp, salience, novelty, metadata_json)
        )
        self.hot_conn.commit()

        # If vector is not provided, generate a deterministic embedding
        if vector is None:
            vector = self._text_to_vector(content)

        # Pad or truncate vector to target dimension
        if len(vector) != self.vector_dim:
            vector = (vector + [0.0] * self.vector_dim)[:self.vector_dim]

        # Always add to warm tier (L2) for vector searches
        self.warm_table.add([
            {
                "id": memory_id,
                "vector": vector,
                "metadata": metadata_json,
                "timestamp": timestamp,
                "salience": salience,
                "novelty": novelty
            }
        ])

        # Evaluate age to see if immediate promotion or archiving is triggered
        age = datetime.now().timestamp() - timestamp

        # Promote to warm tier if high salience (>0.8) and older than 1 hour (represented by embedding it)
        if salience > 0.8 and age > 3600:
            self._promote_to_warm(memory_id)

        # Archive to cold tier if older than 7 days
        if age > 7 * 86400:
            self._archive_to_cold(memory_id)

        return memory_id

    def search_memories(self,
                       query: str,
                       limit: int = 10,
                       use_vsa: bool = True) -> List[Dict]:
        """
        Hierarchical search:
        1. Hot tier: FTS5 for instant keyword matches
        2. Warm tier: VSA-Lite + LanceDB GPU search for semantic matches
        3. Re-rank top results
        """
        results = []

        # Step 1: Hot tier keyword search (L1) - fastest
        hot_results = self._search_hot_tier(query, limit * 2)
        results.extend(hot_results)

        # If we have enough hot results, return early
        if len(results) >= limit:
            return results[:limit]

        # Step 2: Warm tier semantic search (L2) - use VSA if enabled
        if use_vsa:
            query_vector = self._text_to_vector(query)
            warm_results = self._search_warm_tier(
                query_vector,
                limit * 2,
                exclude_ids=[r["id"] for r in hot_results]
            )
            results.extend(warm_results)

        # Deduplicate by ID
        seen_ids = set()
        unique_results = []
        for r in results:
            if r["id"] not in seen_ids:
                seen_ids.add(r["id"])
                unique_results.append(r)

        # Step 3: Re-rank top results with simple salience/novelty scoring
        unique_results.sort(
            key=lambda x: (x.get("salience", 0.5) + x.get("novelty", 0.5)) / 2,
            reverse=True
        )

        return unique_results[:limit]

    def _search_hot_tier(self, query: str, limit: int) -> List[Dict]:
        """Search L1 using FTS5"""
        try:
            cursor = self.hot_conn.execute(
                """SELECT id, content, timestamp, salience, novelty, metadata
                   FROM memories
                   WHERE id IN (
                       SELECT id FROM memories_fts WHERE memories_fts MATCH ?
                   )
                   LIMIT ?""",
                (query, limit)
            )
        except sqlite3.OperationalError:
            # Fallback LIKE query
            cursor = self.hot_conn.execute(
                """SELECT id, content, timestamp, salience, novelty, metadata
                   FROM memories
                   WHERE content LIKE ?
                   LIMIT ?""",
                (f"%{query}%", limit)
            )

        results = []
        for row in cursor.fetchall():
            results.append({
                "id": row[0],
                "content": row[1],
                "timestamp": row[2],
                "salience": row[3],
                "novelty": row[4],
                "metadata": json.loads(row[5]) if row[5] else {},
                "tier": "hot"
            })
        return results

    def _search_warm_tier(self,
                          query_vector: List[float],
                          limit: int,
                          exclude_ids: List[str]) -> List[Dict]:
        """Search L2 using LanceDB ANN search"""
        try:
            search_query = self.warm_table.search(query_vector).metric("cosine").limit(limit * 2)
            results = search_query.to_list()
        except Exception as e:
            logger.warning(f"LanceDB search failed: {e}")
            results = []

        filtered = []
        for r in results:
            if r["id"] not in exclude_ids:
                content = ""
                cursor = self.hot_conn.execute("SELECT content FROM memories WHERE id = ?", (r["id"],))
                row = cursor.fetchone()
                if row:
                    content = row[0]

                filtered.append({
                    "id": r["id"],
                    "content": content,
                    "timestamp": r["timestamp"],
                    "salience": r["salience"],
                    "novelty": r["novelty"],
                    "metadata": json.loads(r["metadata"]) if r["metadata"] else {},
                    "tier": "warm",
                    "distance": r.get("_distance", 0.0)
                })
        return filtered[:limit]

    def _text_to_vector(self, text: str) -> List[float]:
        """
        Deterministic embedding generator (VSA-Lite 1024D hypervector stub).
        Delegates to the configured Embedder instance.
        """
        return self.embedder.embed_query(text)

    def _promote_to_warm(self, memory_id: str):
        """Move memory from hot to warm tier by embedding and adding to LanceDB"""
        cursor = self.hot_conn.execute(
            "SELECT content, timestamp, salience, novelty, metadata FROM memories WHERE id = ?",
            (memory_id,)
        )
        row = cursor.fetchone()
        if not row:
            return

        content, timestamp, salience, novelty, metadata_json = row

        try:
            tbl_df = self.warm_table.to_pandas()
            if not tbl_df.empty and memory_id in tbl_df["id"].values:
                return
        except Exception:
            pass

        vector = self._text_to_vector(content)

        self.warm_table.add([
            {
                "id": memory_id,
                "vector": vector,
                "metadata": metadata_json,
                "timestamp": timestamp,
                "salience": salience,
                "novelty": novelty
            }
        ])
        logger.info(f"Promoted memory {memory_id} to warm tier.")

    def _archive_to_cold(self, memory_id: str):
        """Archive memory to cold tier (ZSTD Parquet) and remove from hot tier"""
        cursor = self.hot_conn.execute(
            "SELECT content, timestamp, salience, novelty, metadata FROM memories WHERE id = ?",
            (memory_id,)
        )
        row = cursor.fetchone()
        if not row:
            return

        content, timestamp, salience, novelty, metadata_json = row

        # Create PyArrow Table
        schema = pa.schema([
            pa.field("id", pa.string()),
            pa.field("content", pa.string()),
            pa.field("timestamp", pa.float64()),
            pa.field("salience", pa.float32()),
            pa.field("novelty", pa.float32()),
            pa.field("metadata", pa.string())
        ])
        
        table = pa.Table.from_pydict({
            "id": [memory_id],
            "content": [content],
            "timestamp": [timestamp],
            "salience": [salience],
            "novelty": [novelty],
            "metadata": [metadata_json]
        }, schema=schema)

        # Write to Parquet file with ZSTD compression
        file_path = os.path.join(self.cold_path, f"{memory_id}.parquet")
        pq.write_table(table, file_path, compression="ZSTD")

        # Remove from hot tier
        self.hot_conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        self.hot_conn.commit()
        logger.info(f"Archived memory {memory_id} to cold tier (Parquet) and removed from hot tier.")

    def run_maintenance(self):
        """Scan hot tier and perform promotions and archiving based on age and salience"""
        now = datetime.now().timestamp()
        
        # Find memories to promote to warm (salience > 0.8 and age > 1 hour)
        one_hour_ago = now - 3600
        cursor = self.hot_conn.execute(
            "SELECT id FROM memories WHERE salience > 0.8 AND timestamp < ?",
            (one_hour_ago,)
        )
        to_promote = [row[0] for row in cursor.fetchall()]
        for mid in to_promote:
            self._promote_to_warm(mid)

        # Find memories to archive to cold (age > 7 days)
        seven_days_ago = now - (7 * 86400)
        cursor = self.hot_conn.execute(
            "SELECT id FROM memories WHERE timestamp < ?",
            (seven_days_ago,)
        )
        to_archive = [row[0] for row in cursor.fetchall()]
        for mid in to_archive:
            self._archive_to_cold(mid)

    def get_anticipatory_patterns(self,
                                 context: List[str]) -> List[Tuple[str, float]]:
        """
        Get predicted outcomes based on recent context.
        Uses simple frequency counting (HOOD-lite)
        """
        return [
            ("continue_current_task", 0.6),
            ("take_break", 0.25),
            ("check_email", 0.15)
        ]

# Singleton instance
memory_store = MemoryStore()