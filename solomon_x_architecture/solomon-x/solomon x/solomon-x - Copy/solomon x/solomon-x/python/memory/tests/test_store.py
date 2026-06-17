import os
import shutil
import pytest
import numpy as np
import pyarrow.parquet as pq
from datetime import datetime
from python.memory.store import MemoryStore

DB_TEST_PATH = "./data/test_memory_db"

@pytest.fixture(autouse=True)
def setup_and_teardown():
    # Cleanup before test
    if os.path.exists(DB_TEST_PATH):
        shutil.rmtree(DB_TEST_PATH)
    
    yield
    
    # Cleanup after test
    if os.path.exists(DB_TEST_PATH):
        shutil.rmtree(DB_TEST_PATH)

def test_store_and_search_hot():
    store = MemoryStore(DB_TEST_PATH)
    content = "User solved Rust lifetime borrowing error"
    metadata = {"salience": 0.5, "novelty": 0.5}
    
    mem_id = store.store_memory(content, metadata=metadata)
    assert mem_id is not None
    assert len(mem_id) == 16
    
    # Check if in L1 sqlite
    cursor = store.hot_conn.execute("SELECT content FROM memories WHERE id = ?", (mem_id,))
    row = cursor.fetchone()
    assert row is not None
    assert row[0] == content

    # Search keyword
    results = store.search_memories("Rust", limit=3)
    assert len(results) > 0
    assert results[0]["id"] == mem_id
    assert results[0]["content"] == content
    assert results[0]["tier"] == "hot"

def test_deterministic_embedding():
    store = MemoryStore(DB_TEST_PATH)
    text = "test deterministic embedding"
    
    vec1 = store._text_to_vector(text)
    vec2 = store._text_to_vector(text)
    vec3 = store._text_to_vector("different text")
    
    assert vec1 == vec2
    assert vec1 != vec3
    assert len(vec1) == 1024
    
    # Assert unit length (norm close to 1.0)
    norm = np.linalg.norm(vec1)
    assert pytest.approx(norm, abs=1e-5) == 1.0

def test_promote_to_warm():
    store = MemoryStore(DB_TEST_PATH)
    content = "Promote this memory to warm tier"
    
    mem_id = store.store_memory(content, metadata={"salience": 0.9})
    store._promote_to_warm(mem_id)
    
    # Warm table should contain the ID
    warm_df = store.warm_table.to_pandas()
    assert mem_id in warm_df["id"].values

def test_archive_to_cold():
    store = MemoryStore(DB_TEST_PATH)
    content = "Archive this memory to cold tier"
    
    mem_id = store.store_memory(content, metadata={"salience": 0.3})
    store._archive_to_cold(mem_id)
    
    # Verify file exists
    parquet_file = os.path.join(store.cold_path, f"{mem_id}.parquet")
    assert os.path.exists(parquet_file)
    
    # Verify file is readable Parquet and matches content
    table = pq.read_table(parquet_file)
    assert table.num_rows == 1
    assert table.to_pydict()["content"][0] == content
    
    # Verify removed from hot tier
    cursor = store.hot_conn.execute("SELECT id FROM memories WHERE id = ?", (mem_id,))
    assert cursor.fetchone() is None

def test_maintenance_flow():
    store = MemoryStore(DB_TEST_PATH)
    
    # 1. Memory for promotion (salience > 0.8, age > 1 hour)
    promo_time = datetime.now().timestamp() - 4000
    promo_id = store.store_memory(
        "Highly salient older memory", 
        metadata={"salience": 0.9, "timestamp": promo_time}
    )
    
    # 2. Memory for archiving (age > 7 days)
    archive_time = datetime.now().timestamp() - (8 * 86400)
    archive_id = store.store_memory(
        "Very old cold archive memory", 
        metadata={"salience": 0.2, "timestamp": archive_time}
    )
    
    # Run maintenance
    store.run_maintenance()
    
    # Verify promo memory is in warm tier (LanceDB)
    warm_df = store.warm_table.to_pandas()
    assert promo_id in warm_df["id"].values
    
    # Verify archive memory is archived (Parquet file exists)
    parquet_file = os.path.join(store.cold_path, f"{archive_id}.parquet")
    assert os.path.exists(parquet_file)
    
    # Verify archive memory is removed from SQLite
    cursor = store.hot_conn.execute("SELECT id FROM memories WHERE id = ?", (archive_id,))
    assert cursor.fetchone() is None
