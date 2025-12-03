#!/usr/bin/env python3
"""Small TCP server that emits newline-delimited JSON for local testing.

Usage: python scripts/demo_server.py [host] [port] [count]
Example: python scripts/demo_server.py 127.0.0.1 9999 100
"""
import socket
import sys
import json
import time
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


def run(host: str = "127.0.0.1", port: int = 9999, count: int = 100):
    """Run demo TCP server that emits newline-delimited JSON events.
    
    Args:
        host: Host address to bind to
        port: Port number to listen on
        count: Number of events to send to each client
    """
    addr = (host, port)
    srv = None
    
    try:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # Set timeout to allow keyboard interrupt
        srv.settimeout(1.0)
        
        try:
            srv.bind(addr)
        except OSError as e:
            logger.error(f"Failed to bind to {host}:{port} - {e}")
            logger.error("Port may already be in use. Try a different port.")
            return 1
            
        srv.listen(1)
        logger.info(f"Demo server listening on {host}:{port}")
        logger.info(f"Waiting for client connection... (Press Ctrl+C to stop)")
        
        while True:
            try:
                conn, peer = srv.accept()
                logger.info(f"Client connected from {peer[0]}:{peer[1]}")
                
                try:
                    # Send events to client
                    for i in range(count):
                        obj = {"ts": time.time(), "seq": i, "msg": f"event-{i}"}
                        line = json.dumps(obj) + "\n"
                        
                        try:
                            conn.sendall(line.encode("utf-8"))
                            time.sleep(0.01)
                        except (BrokenPipeError, ConnectionResetError):
                            logger.warning(f"Client {peer[0]}:{peer[1]} disconnected during transmission")
                            break
                    else:
                        logger.info(f"Successfully sent {count} events to {peer[0]}:{peer[1]}")
                        
                except Exception as e:
                    logger.error(f"Error handling client {peer}: {e}")
                finally:
                    conn.close()
                    logger.info(f"Connection closed with {peer[0]}:{peer[1]}")
                    
            except socket.timeout:
                # Timeout allows checking for KeyboardInterrupt
                continue
            except KeyboardInterrupt:
                logger.info("Received shutdown signal")
                break
            except Exception as e:
                logger.error(f"Error accepting connection: {e}")
                break
                
    except KeyboardInterrupt:
        logger.info("Server interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1
    finally:
        if srv:
            srv.close()
            logger.info("Server socket closed")
    
    return 0


if __name__ == "__main__":
    try:
        host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
        port = int(sys.argv[2]) if len(sys.argv) > 2 else 9999
        count = int(sys.argv[3]) if len(sys.argv) > 3 else 100
        
        logger.info(f"Starting demo server with host={host}, port={port}, count={count}")
        exit_code = run(host, port, count)
        sys.exit(exit_code)
        
    except ValueError as e:
        logger.error(f"Invalid argument: {e}")
        logger.error("Usage: python scripts/demo_server.py [host] [port] [count]")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
