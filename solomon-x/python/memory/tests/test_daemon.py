import json
import struct
import sys
import socket
from unittest.mock import patch, MagicMock, call
import pytest

from python.memory.daemon import SolomonBusClient, run_daemon

@patch('sys.platform', 'linux')
@patch('os.path.exists')
@patch('socket.socket')
def test_client_connect_unix(mock_socket, mock_exists):
    mock_exists.return_value = True

    client = SolomonBusClient("test_socket")
    assert not client.is_windows

    mock_conn = MagicMock()
    mock_socket.return_value = mock_conn

    success = client.connect()

    assert success is True
    mock_socket.assert_called_once_with(socket.AF_UNIX, socket.SOCK_STREAM)
    mock_conn.connect.assert_called_once_with("test_socket")
    assert client.conn == mock_conn

@patch('sys.platform', 'linux')
@patch('os.path.exists')
@patch('socket.socket')
def test_client_connect_unix_fallback(mock_socket, mock_exists):
    mock_exists.return_value = False

    client = SolomonBusClient("test_socket")

    mock_conn = MagicMock()
    mock_socket.return_value = mock_conn

    success = client.connect()

    assert success is True
    import os
    mock_conn.connect.assert_called_once_with(os.path.join("/tmp", "test_socket"))

@patch('sys.platform', 'win32')
def test_client_connect_windows():
    mock_ctypes = MagicMock()
    mock_ctypes.windll.kernel32.CreateFileW.return_value = 12345 # Valid handle

    with patch.dict('sys.modules', {'ctypes': mock_ctypes}):
        client = SolomonBusClient("test_pipe")
        assert client.is_windows is True

        success = client.connect()

        assert success is True
        mock_ctypes.windll.kernel32.CreateFileW.assert_called_once()
        assert client.handle == 12345

@patch('sys.platform', 'win32')
def test_client_connect_windows_fail():
    mock_ctypes = MagicMock()
    mock_ctypes.windll.kernel32.CreateFileW.return_value = -1 # INVALID_HANDLE_VALUE

    with patch.dict('sys.modules', {'ctypes': mock_ctypes}):
        client = SolomonBusClient("test_pipe")

        success = client.connect()

        assert success is False

@patch('sys.platform', 'linux')
def test_send_envelope_unix():
    client = SolomonBusClient("test_socket")
    client.is_windows = False
    client.conn = MagicMock()

    payload = b"hello world"
    counter = 42

    success = client.send_envelope(counter, payload)

    assert success is True

    # Check what was sent
    call_args = client.conn.sendall.call_args[0][0]
    length = struct.unpack("<I", call_args[:4])[0]

    envelope_bytes = call_args[4:]
    assert len(envelope_bytes) == length

    envelope = json.loads(envelope_bytes.decode("utf-8"))
    assert envelope["counter"] == counter
    assert envelope["payload"] == list(payload)
    assert len(envelope["signature"]) == 64

@patch('sys.platform', 'linux')
def test_receive_envelope_unix():
    client = SolomonBusClient("test_socket")
    client.is_windows = False
    client.conn = MagicMock()

    payload = b"response data"
    counter = 100

    envelope = {
        "counter": counter,
        "signature": [0] * 64,
        "payload": list(payload)
    }
    envelope_bytes = json.dumps(envelope).encode("utf-8")
    length = len(envelope_bytes)
    length_prefix = struct.pack("<I", length)

    # Mock recv to return length first, then the envelope bytes
    client.conn.recv.side_effect = [length_prefix, envelope_bytes]

    received = client.receive_envelope()

    assert received is not None
    assert received["counter"] == counter
    assert received["payload"] == payload

@patch('sys.platform', 'linux')
def test_close_unix():
    client = SolomonBusClient("test_socket")
    client.is_windows = False
    mock_conn = MagicMock()
    client.conn = mock_conn

    client.close()

    mock_conn.close.assert_called_once()
    assert client.conn is None

@patch('python.memory.daemon.MemoryStore')
@patch('python.memory.daemon.SolomonBusClient')
def test_run_daemon_connection_failure(mock_client_class, mock_store_class):
    mock_client = MagicMock()
    mock_client.connect.return_value = False
    mock_client_class.return_value = mock_client

    with patch('time.sleep') as mock_sleep:
        run_daemon()

    assert mock_client.connect.call_count == 5
    assert mock_sleep.call_count == 5
    mock_client.receive_envelope.assert_not_called()

@patch('python.memory.daemon.MemoryStore')
@patch('python.memory.daemon.SolomonBusClient')
def test_run_daemon_memory_store_event(mock_client_class, mock_store_class):
    mock_client = MagicMock()
    mock_client.connect.return_value = True
    mock_client_class.return_value = mock_client

    mock_store = MagicMock()
    mock_store.store_memory.return_value = "mem_123"
    mock_store_class.return_value = mock_store

    # Send store event, then simulate disconnect by returning None
    store_event = {
        "event": "memory.store",
        "content": "test memory content",
        "metadata": {"source": "test"}
    }

    payload = json.dumps(store_event).encode("utf-8")

    mock_client.receive_envelope.side_effect = [
        {"counter": 1, "payload": payload},
        None # End loop
    ]

    run_daemon()

    mock_store.store_memory.assert_called_once_with("test memory content", metadata={"source": "test"})

    # Check response sent
    mock_client.send_envelope.assert_called_once()
    call_args = mock_client.send_envelope.call_args[0]
    assert call_args[0] == 2 # counter + 1

    response = json.loads(call_args[1].decode("utf-8"))
    assert response["event"] == "memory.store_response"
    assert response["status"] == "success"
    assert response["memory_id"] == "mem_123"

    mock_client.close.assert_called_once()

@patch('python.memory.daemon.MemoryStore')
@patch('python.memory.daemon.SolomonBusClient')
def test_run_daemon_memory_search_event(mock_client_class, mock_store_class):
    mock_client = MagicMock()
    mock_client.connect.return_value = True
    mock_client_class.return_value = mock_client

    mock_store = MagicMock()
    mock_store.search_memories.return_value = [
        {"id": "mem_1", "content": "result 1", "timestamp": 12345, "salience": 0.9, "novelty": 0.5, "metadata": {}, "tier": "hot", "distance": 0.1}
    ]
    mock_store_class.return_value = mock_store

    search_event = {
        "event": "memory.search",
        "query": "find me",
        "limit": 10
    }

    payload = json.dumps(search_event).encode("utf-8")

    mock_client.receive_envelope.side_effect = [
        {"counter": 5, "payload": payload},
        None # End loop
    ]

    run_daemon()

    mock_store.search_memories.assert_called_once_with("find me", limit=10)

    # Check response sent
    mock_client.send_envelope.assert_called_once()
    call_args = mock_client.send_envelope.call_args[0]
    assert call_args[0] == 6 # counter + 1

    response = json.loads(call_args[1].decode("utf-8"))
    assert response["event"] == "memory.search_response"
    assert response["status"] == "success"
    assert len(response["results"]) == 1
    assert response["results"][0]["id"] == "mem_1"

@patch('python.memory.daemon.MemoryStore')
@patch('python.memory.daemon.SolomonBusClient')
def test_run_daemon_invalid_event_continues(mock_client_class, mock_store_class):
    mock_client = MagicMock()
    mock_client.connect.return_value = True
    mock_client_class.return_value = mock_client

    invalid_event = {"event": "unknown_event"}
    invalid_payload = json.dumps(invalid_event).encode("utf-8")

    malformed_payload = b"not a json object"

    mock_client.receive_envelope.side_effect = [
        {"counter": 1, "payload": invalid_payload},
        {"counter": 2, "payload": malformed_payload},
        None # End loop
    ]

    run_daemon()

    # Loop should have consumed all 3 items and then exited without crashing
    assert mock_client.receive_envelope.call_count == 3
    mock_client.send_envelope.assert_not_called()
    mock_client.close.assert_called_once()
