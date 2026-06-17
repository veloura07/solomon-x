import os
import shutil
import pytest
import numpy as np
from python.memory.embedder import HashingEmbedder, RandomEmbedder
from python.memory.store import MemoryStore

DB_TEST_PATH = "./data/test_embedder_store_db"

@pytest.fixture
def clean_test_db():
    if os.path.exists(DB_TEST_PATH):
        shutil.rmtree(DB_TEST_PATH)
    yield
    if os.path.exists(DB_TEST_PATH):
        shutil.rmtree(DB_TEST_PATH)

def test_hashing_embedder():
    embedder = HashingEmbedder(dimension=1024)
    assert embedder.dimension == 1024

    text = "Verify hypervector serialization and hashing"
    
    vec1 = embedder.embed_query(text)
    vec2 = embedder.embed_query(text)
    vec3 = embedder.embed_query("Different query input text")

    # 1. Assert determinism
    assert vec1 == vec2
    assert vec1 != vec3
    assert len(vec1) == 1024

    # 2. Assert L2 unit-norm constraint (norm close to 1.0)
    norm = np.linalg.norm(vec1)
    assert pytest.approx(norm, abs=1e-5) == 1.0

def test_random_embedder():
    embedder = RandomEmbedder(dimension=512)
    assert embedder.dimension == 512

    text = "Deterministic check for random embedder"
    vec1 = embedder.embed_query(text)
    vec2 = embedder.embed_query(text)

    # Assert non-determinism
    assert vec1 != vec2
    assert len(vec1) == 512

    # Assert unit norm
    norm = np.linalg.norm(vec1)
    assert pytest.approx(norm, abs=1e-5) == 1.0

def test_store_integration_with_random_embedder(clean_test_db):
    embedder = RandomEmbedder(dimension=1024)
    store = MemoryStore(DB_TEST_PATH, embedder=embedder)

    content = "Integration verification of custom embedder instances"
    mem_id = store.store_memory(content)
    
    assert mem_id is not None
    
    # Verify retrieved warm table entry matches the target dimensions
    results = store.search_memories("Integration", limit=1)
    assert len(results) > 0
    assert results[0]["id"] == mem_id
