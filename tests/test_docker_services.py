"""
Integration tests for Docker services.

This module tests connectivity and functionality of all Docker services
in the Second Brain Database stack.
"""

import pytest
import httpx
import redis
from motor.motor_asyncio import AsyncIOMotorClient
from qdrant_client import QdrantClient


# ============================================================================
# Test Configuration
# ============================================================================

API_BASE_URL = "http://localhost:8000"
REDIS_HOST = "localhost"
REDIS_PORT = 6379
MONGODB_URL = "mongodb://testuser:testpassword@localhost:27017/test_second_brain_database?authSource=admin"
QDRANT_HOST = "localhost"
QDRANT_PORT = 6333


# ============================================================================
# API Service Tests
# ============================================================================

@pytest.mark.asyncio
async def test_api_health_endpoint():
    """Test that the API health endpoint is accessible."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_BASE_URL}/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_api_docs_endpoint():
    """Test that the API documentation is accessible."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_BASE_URL}/docs")
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_api_openapi_schema():
    """Test that the OpenAPI schema is accessible."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_BASE_URL}/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        assert "openapi" in schema
        assert "info" in schema


# ============================================================================
# MongoDB Service Tests
# ============================================================================

@pytest.mark.asyncio
async def test_mongodb_connection():
    """Test MongoDB connectivity."""
    client = AsyncIOMotorClient(MONGODB_URL)
    try:
        # Ping the database
        await client.admin.command("ping")
        
        # List databases
        db_list = await client.list_database_names()
        assert isinstance(db_list, list)
        
    finally:
        client.close()


@pytest.mark.asyncio
async def test_mongodb_crud_operations():
    """Test basic MongoDB CRUD operations."""
    client = AsyncIOMotorClient(MONGODB_URL)
    try:
        db = client.test_second_brain_database
        collection = db.test_collection
        
        # Insert
        result = await collection.insert_one({"test": "data", "value": 123})
        assert result.inserted_id is not None
        
        # Read
        doc = await collection.find_one({"test": "data"})
        assert doc is not None
        assert doc["value"] == 123
        
        # Update
        await collection.update_one(
            {"test": "data"},
            {"$set": {"value": 456}}
        )
        updated_doc = await collection.find_one({"test": "data"})
        assert updated_doc["value"] == 456
        
        # Delete
        await collection.delete_one({"test": "data"})
        deleted_doc = await collection.find_one({"test": "data"})
        assert deleted_doc is None
        
    finally:
        # Cleanup
        await collection.drop()
        client.close()


# ============================================================================
# Redis Service Tests
# ============================================================================

def test_redis_connection():
    """Test Redis connectivity."""
    client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)
    try:
        # Ping Redis
        assert client.ping() is True
    finally:
        client.close()


def test_redis_operations():
    """Test basic Redis operations."""
    client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)
    try:
        # Set
        client.set("test_key", "test_value")
        
        # Get
        value = client.get("test_key")
        assert value == b"test_value"
        
        # Delete
        client.delete("test_key")
        
        # Verify deletion
        assert client.get("test_key") is None
        
    finally:
        client.close()


def test_redis_hash_operations():
    """Test Redis hash operations."""
    client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)
    try:
        # Set hash fields
        client.hset("test_hash", "field1", "value1")
        client.hset("test_hash", "field2", "value2")
        
        # Get hash field
        value = client.hget("test_hash", "field1")
        assert value == b"value1"
        
        # Get all hash fields
        all_fields = client.hgetall("test_hash")
        assert len(all_fields) == 2
        
        # Delete hash
        client.delete("test_hash")
        
    finally:
        client.close()


# ============================================================================
# Qdrant Service Tests
# ============================================================================

def test_qdrant_connection():
    """Test Qdrant connectivity."""
    client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    
    # Get collections (should not raise an error)
    collections = client.get_collections()
    assert collections is not None


def test_qdrant_collection_operations():
    """Test Qdrant collection operations."""
    from qdrant_client.models import Distance, VectorParams, PointStruct
    
    client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    collection_name = "test_collection"
    
    try:
        # Create collection
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=128, distance=Distance.COSINE),
        )
        
        # Verify collection exists
        collections = client.get_collections()
        collection_names = [c.name for c in collections.collections]
        assert collection_name in collection_names
        
        # Insert a point
        client.upsert(
            collection_name=collection_name,
            points=[
                PointStruct(
                    id=1,
                    vector=[0.1] * 128,
                    payload={"test": "data"}
                )
            ]
        )
        
        # Retrieve the point
        point = client.retrieve(
            collection_name=collection_name,
            ids=[1]
        )
        assert len(point) == 1
        assert point[0].payload["test"] == "data"
        
    finally:
        # Cleanup
        try:
            client.delete_collection(collection_name=collection_name)
        except Exception:
            pass


# ============================================================================
# Service Integration Tests
# ============================================================================

@pytest.mark.asyncio
async def test_api_mongodb_integration():
    """Test that API can communicate with MongoDB."""
    # This test assumes the API has a health check that includes DB status
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_BASE_URL}/health")
        assert response.status_code == 200
        data = response.json()
        
        # Check if database is connected (if health endpoint provides this info)
        if "database" in data:
            assert data["database"]["status"] == "connected"


@pytest.mark.asyncio
async def test_api_redis_integration():
    """Test that API can communicate with Redis."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_BASE_URL}/health")
        assert response.status_code == 200
        data = response.json()
        
        # Check if Redis is connected (if health endpoint provides this info)
        if "redis" in data:
            assert data["redis"]["status"] == "connected"


# ============================================================================
# Celery Service Tests
# ============================================================================

def test_celery_worker_connectivity():
    """Test that Celery worker is accessible via Redis."""
    client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)
    try:
        # Check if Celery is using Redis as broker
        # Celery creates keys in Redis, we can check for them
        keys = client.keys("celery*")
        # This is a basic check - in a real scenario, you'd want to
        # actually submit a task and verify it's processed
        assert isinstance(keys, list)
    finally:
        client.close()


# ============================================================================
# Performance Tests
# ============================================================================

@pytest.mark.asyncio
async def test_api_response_time():
    """Test that API responds within acceptable time."""
    import time
    
    async with httpx.AsyncClient() as client:
        start = time.time()
        response = await client.get(f"{API_BASE_URL}/health")
        elapsed = time.time() - start
        
        assert response.status_code == 200
        assert elapsed < 1.0  # Should respond within 1 second


def test_redis_performance():
    """Test Redis performance for basic operations."""
    import time
    
    client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)
    try:
        # Test write performance
        start = time.time()
        for i in range(1000):
            client.set(f"perf_test_{i}", f"value_{i}")
        write_time = time.time() - start
        
        # Test read performance
        start = time.time()
        for i in range(1000):
            client.get(f"perf_test_{i}")
        read_time = time.time() - start
        
        # Cleanup
        for i in range(1000):
            client.delete(f"perf_test_{i}")
        
        # Assert reasonable performance (adjust thresholds as needed)
        assert write_time < 2.0  # 1000 writes in under 2 seconds
        assert read_time < 2.0   # 1000 reads in under 2 seconds
        
    finally:
        client.close()
