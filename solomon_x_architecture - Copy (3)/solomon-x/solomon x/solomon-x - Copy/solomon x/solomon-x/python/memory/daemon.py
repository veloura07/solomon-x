import os
import sys
import json
import time
import socket
import struct
import logging
from typing import Dict, Any, List, Optional
from python.memory.store import MemoryStore

logger = logging.getLogger("solomon.memory.daemon")

class SolomonBusClient:
    """
    Python client for the Solomon X inter-process bus.
    Supports AF_UNIX Domain Sockets on Linux/macOS and Named Pipes on Windows.
    """
    def __init__(self, address: str = "solomon_bus") -> None:
        self.address = address
        self.is_windows = sys.platform == "win32"
        self.conn = None
        self.handle = None

    def connect(self) -> bool:
        if self.is_windows:
            return self._connect_windows()
        else:
            return self._connect_unix()

    def _connect_windows(self) -> bool:
        import ctypes
        pipe_path = f"\\\\.\\pipe\\{self.address}"
        
        GENERIC_READ = 0x80000000
        GENERIC_WRITE = 0x40000000
        OPEN_EXISTING = 3
        
        try:
            self.handle = ctypes.windll.kernel32.CreateFileW(
                pipe_path,
                GENERIC_READ | GENERIC_WRITE,
                0,
                None,
                OPEN_EXISTING,
                0,
                None
            )
            if self.handle == -1: # INVALID_HANDLE_VALUE
                logger.error(f"Failed to open named pipe: {pipe_path}")
                return False
            logger.info(f"Connected to Windows Named Pipe: {pipe_path}")
            return True
        except Exception as e:
            logger.error(f"Named pipe connection failed: {e}")
            return False

    def _connect_unix(self) -> bool:
        socket_path = self.address
        if not os.path.exists(socket_path):
            socket_path = os.path.join("/tmp", self.address)
            
        try:
            self.conn = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.conn.connect(socket_path)
            logger.info(f"Connected to Unix Domain Socket: {socket_path}")
            return True
        except Exception as e:
            logger.error(f"Unix domain socket connection failed: {e}")
            return False

    def send_envelope(self, counter: int, payload: bytes) -> bool:
        # Create JSON envelope matching Rust MessageEnvelope serialization scheme
        envelope = {
            "counter": counter,
            "signature": [0] * 64, # Mock signature payload
            "payload": list(payload)
        }
        serialized = json.dumps(envelope).encode("utf-8")
        length = len(serialized)
        
        try:
            length_prefix = struct.pack("<I", length) # 4-byte little endian
            if self.is_windows:
                import ctypes
                written = ctypes.c_ulong(0)
                # Write length prefix
                ctypes.windll.kernel32.WriteFile(self.handle, length_prefix, 4, ctypes.byref(written), None)
                # Write serialized payload
                ctypes.windll.kernel32.WriteFile(self.handle, serialized, length, ctypes.byref(written), None)
            else:
                self.conn.sendall(length_prefix + serialized)
            return True
        except Exception as e:
            logger.error(f"Failed to send envelope: {e}")
            return False

    def receive_envelope(self) -> Optional[Dict[str, Any]]:
        try:
            if self.is_windows:
                import ctypes
                read_bytes = ctypes.c_ulong(0)
                length_buf = ctypes.create_string_buffer(4)
                
                res = ctypes.windll.kernel32.ReadFile(self.handle, length_buf, 4, ctypes.byref(read_bytes), None)
                if not res or read_bytes.value != 4:
                    return None
                
                length = struct.unpack("<I", length_buf.raw)[0]
                
                payload_buf = ctypes.create_string_buffer(length)
                res = ctypes.windll.kernel32.ReadFile(self.handle, payload_buf, length, ctypes.byref(read_bytes), None)
                if not res or read_bytes.value != length:
                    return None
                
                envelope_bytes = payload_buf.raw[:length]
            else:
                length_buf = self.conn.recv(4)
                if len(length_buf) != 4:
                    return None
                length = struct.unpack("<I", length_buf)[0]
                
                envelope_bytes = bytearray()
                while len(envelope_bytes) < length:
                    chunk = self.conn.recv(length - len(envelope_bytes))
                    if not chunk:
                        break
                    envelope_bytes.extend(chunk)
                    
            envelope = json.loads(envelope_bytes.decode("utf-8"))
            # Convert payload from list of integers back to bytes
            envelope["payload"] = bytes(envelope["payload"])
            return envelope
        except Exception as e:
            logger.error(f"Failed to receive envelope: {e}")
            return None

    def close(self):
        if self.is_windows and self.handle:
            import ctypes
            ctypes.windll.kernel32.CloseHandle(self.handle)
            self.handle = None
        elif self.conn:
            self.conn.close()
            self.conn = None

def run_daemon():
    logging.basicConfig(level=logging.INFO)
    logger.info("Starting MemoryOS Bus-Resident Daemon listener...")

    store = MemoryStore()
    client = SolomonBusClient("solomon_bus")
    
    # Loop retrying connection in the background
    connected = False
    for attempt in range(5):
        if client.connect():
            connected = True
            break
        logger.info(f"Bus connection attempt {attempt+1}/5 failed. Retrying in 1 second...")
        time.sleep(1)
        
    if not connected:
        logger.warning("Could not establish connection to the IPC bus. Daemon operating in idle self-test mode.")
        return

    try:
        while True:
            envelope = client.receive_envelope()
            if not envelope:
                logger.info("Bus connection closed. Exiting daemon loop.")
                break
                
            payload = envelope["payload"]
            counter = envelope["counter"]
            
            try:
                msg = json.loads(payload.decode("utf-8"))
                event = msg.get("event")
                
                if event == "memory.store":
                    content = msg.get("content", "")
                    metadata = msg.get("metadata", {})
                    logger.info(f"Processing store request. Content length: {len(content)}")
                    
                    mem_id = store.store_memory(content, metadata=metadata)
                    
                    response = json.dumps({
                        "event": "memory.store_response",
                        "status": "success",
                        "memory_id": mem_id
                    }).encode("utf-8")
                    client.send_envelope(counter + 1, response)
                    
                elif event == "memory.search":
                    query = msg.get("query", "")
                    limit = msg.get("limit", 5)
                    logger.info(f"Processing search query: '{query}' (limit: {limit})")
                    
                    results = store.search_memories(query, limit=limit)
                    
                    serializable_results = []
                    for r in results:
                        serializable_results.append({
                            "id": r["id"],
                            "content": r["content"],
                            "timestamp": r["timestamp"],
                            "salience": r["salience"],
                            "novelty": r["novelty"],
                            "metadata": r["metadata"],
                            "tier": r["tier"],
                            "distance": r.get("distance", 0.0)
                        })
                        
                    response = json.dumps({
                        "event": "memory.search_response",
                        "status": "success",
                        "results": serializable_results
                    }).encode("utf-8")
                    client.send_envelope(counter + 1, response)
                    
                else:
                    logger.warning(f"Unrecognized daemon event: {event}")
            except Exception as e:
                logger.error(f"Error handling event payload: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    run_daemon()
