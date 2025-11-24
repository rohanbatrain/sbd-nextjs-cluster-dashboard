import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import Response

from second_brain_database.managers.cluster_manager import ClusterManager
from second_brain_database.models.cluster_models import (
    ClusterNode,
    NodeRole,
    NodeStatus,
    ReplicationEvent,
)
from second_brain_database.services.owner_validation_service import OwnerValidationService
from second_brain_database.services.replication_service import ReplicationService


@pytest.fixture
def mock_db_manager():
    with patch("second_brain_database.managers.cluster_manager.db_manager") as mock:
        mock.get_collection.return_value = AsyncMock()
        yield mock


@pytest.fixture
def mock_settings():
    with patch("second_brain_database.managers.cluster_manager.settings") as mock:
        mock.CLUSTER_ENABLED = True
        mock.CLUSTER_NODE_ID = "test-node-1"
        mock.CLUSTER_NODE_ROLE = "master"
        mock.CLUSTER_HEARTBEAT_INTERVAL = 1
        mock.CLUSTER_AUTH_TOKEN = MagicMock()
        mock.CLUSTER_AUTH_TOKEN.get_secret_value.return_value = "secret-token"
        mock.CLUSTER_ADVERTISE_ADDRESS = "localhost"
        mock.PORT = 8000
        mock.cluster_is_master = True
        yield mock


@pytest.mark.asyncio
async def test_register_node(mock_db_manager, mock_settings):
    """Test node registration logic."""
    manager = ClusterManager()
    
    # Mock collection
    collection = mock_db_manager.get_collection.return_value
    collection.update_one.return_value = AsyncMock(upserted_id="test-id")
    
    # Register node
    manager.node_id = "test-node-1"
    with patch("second_brain_database.managers.cluster_manager.cluster_audit_service") as mock_audit:
        mock_audit.log_event = AsyncMock()
        
        node_id = await manager.register_node(
            hostname="localhost",
            port=8000,
            owner_user_id="user-123"
        )
        
        assert node_id == "test-node-1"
        assert collection.update_one.call_count == 2
        
        # Verify first update (registration)
        call_args = collection.update_one.call_args_list[0]
        assert call_args[0][0]["node_id"] == "test-node-1"
        assert call_args[0][1]["$set"]["role"] == "master"
        assert call_args[0][1]["$set"]["status"] == NodeStatus.JOINING
        
        # Verify second update (status change to healthy)
        call_args_2 = collection.update_one.call_args_list[1]
        assert call_args_2[0][0]["node_id"] == "test-node-1"
        assert call_args_2[0][1]["$set"]["status"] == NodeStatus.HEALTHY


@pytest.mark.asyncio
async def test_replication_capture(mock_db_manager):
    """Test capturing replication events."""
    with patch("second_brain_database.services.replication_service.settings") as mock_settings:
        mock_settings.CLUSTER_ENABLED = True
        mock_settings.CLUSTER_REPLICATION_ENABLED = True
        mock_settings.cluster_is_master = True
        
        # Patch cluster_manager
        with patch("second_brain_database.services.replication_service.cluster_manager") as mock_cm:
            mock_cm.node_id = "node-1"  # Set node_id to avoid validation error
            
            # Patch db_manager in replication service
            with patch("second_brain_database.services.replication_service.db_manager", mock_db_manager):
                service = ReplicationService()
                
                # Mock dependencies
                service._publish_event = AsyncMock()
                service._get_replication_targets = AsyncMock(return_value=[
                    ClusterNode(
                        node_id="node-2", 
                        hostname="localhost", 
                        port=8001, 
                        role=NodeRole.REPLICA,
                        status=NodeStatus.HEALTHY
                    )
                ])
                
                # Capture event
                event_id = await service.capture_event(
                    operation="insert",
                    collection="users",
                    document_id="doc-1",
                    data={"name": "Test User"}
                )
                
                assert event_id.startswith("evt-")
                
                # Verify log insertion
                log_collection = mock_db_manager.get_collection.return_value
                log_collection.insert_one.assert_called_once()
                
                # Verify publish
                service._publish_event.assert_called_once()


@pytest.mark.asyncio
async def test_owner_validation_distributed():
    """Test distributed owner validation."""
    service = OwnerValidationService()
    
    # Mock local check
    service._check_local_owner = AsyncMock(return_value=True)
    
    # Mock remote check
    service._check_remote_owner = AsyncMock(return_value=True)
    
    # Mock cluster manager
    with patch("second_brain_database.services.owner_validation_service.cluster_manager") as mock_cm:
        mock_cm.node_id = "node-1"
        # list_nodes is async, so return_value should be the list, but when called it should be awaitable
        # AsyncMock handles this automatically if we set return_value
        mock_cm.list_nodes = AsyncMock(return_value=[
            ClusterNode(node_id="node-1", hostname="h1", port=8000, status=NodeStatus.HEALTHY),
            ClusterNode(node_id="node-2", hostname="h2", port=8000, status=NodeStatus.HEALTHY),
        ])
        mock_cm.get_node = AsyncMock(side_effect=lambda nid: ClusterNode(node_id=nid, hostname="h", port=8000))
        
        result = await service.validate_owner_across_cluster("user-123")
        
        assert result.is_valid is True
        assert result.total_nodes == 2
        assert result.validated_nodes == 2
        assert len(result.failed_nodes) == 0
        
        service._check_local_owner.assert_called_once_with("user-123")
        service._check_remote_owner.assert_called_once()


@pytest.mark.asyncio
async def test_leader_election(mock_db_manager):
    """Test leader election logic."""
    manager = ClusterManager()
    manager.node_id = "node-1"
    
    # Mock nodes
    nodes = [
        ClusterNode(
            node_id="node-1", 
            hostname="h1", 
            port=8000, 
            role=NodeRole.MASTER,
            capabilities={"priority": 100}
        ),
        ClusterNode(
            node_id="node-2", 
            hostname="h2", 
            port=8000, 
            role=NodeRole.MASTER,
            capabilities={"priority": 90}
        ),
    ]
    
    manager.list_nodes = AsyncMock(return_value=nodes)
    
    with patch("second_brain_database.managers.cluster_manager.cluster_audit_service") as mock_audit:
        mock_audit.log_event = AsyncMock()
        
        leader_id = await manager.elect_leader()
        
        assert leader_id == "node-1"
        assert manager._current_leader == "node-1"
        mock_audit.log_event.assert_called_once()
