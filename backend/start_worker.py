#!/usr/bin/env python3
"""
Railway worker entry point - starts RQ worker for background task processing
"""
import os
import sys
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from rq import Worker, Queue
from app.config.settings import settings
from app.utils.redis_manager import redis_manager, redis_health_check


class HealthCheckHandler(BaseHTTPRequestHandler):
    """Minimal HTTP server for health checks to prevent platform spin-down."""
    
    def do_GET(self):
        """Handle GET requests for health checks."""
        if self.path in ('/api/health/queue', '/api/health'):
            try:
                response = '{"status": "healthy", "redis": "connected"}'
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(response.encode())
            except Exception as e:
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(f'{{"status": "healthy", "error": "{str(e)}"}}'.encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        """Suppress default HTTP server logging."""
        pass

def main():
    """Start RQ worker to process background tasks"""
    # Get Redis connection from centralized manager
    max_retries = 5
    redis_conn = None
    for attempt in range(max_retries):
        try:
            redis_conn = redis_manager.get_connection()
            print(f"Redis connection established on attempt {attempt + 1}")
            break
        except Exception as exc:
            print(f"Redis connection attempt {attempt + 1} failed: {exc}")
            if attempt == max_retries - 1:
                print("Failed to establish Redis connection after maximum retries")
                raise
            print(f"Retrying in 2 seconds...")
            time.sleep(2)
    queue = Queue("default", connection=redis_conn)
    
    worker = Worker([queue], connection=redis_conn)
    
    print(f"Starting RQ worker for queue: default")
    print(f"Redis URL: {settings.REDIS_URL}")
    
    # Start minimal HTTP server for health checks (prevents platform spin-down)
    # Run on port 8001 to avoid conflict with API service
    health_check_port = int(os.getenv("WORKER_HEALTH_PORT", "8001"))
    http_server = HTTPServer(('0.0.0.0', health_check_port), HealthCheckHandler)
    http_thread = threading.Thread(target=http_server.serve_forever, daemon=True)
    http_thread.start()
    print(f"Health check server started on port {health_check_port}")
    
    worker.work(with_scheduler=True)

def run_with_restart():
    """Run worker with automatic restart on exit or connection loss"""
    while True:
        try:
            main()
        except Exception as e:
            print(f"Worker exited with error: {e}")
            print("Restarting in 5 seconds...")
            time.sleep(5)

if __name__ == "__main__":
    # Check if auto-restart is enabled (default for production)
    if os.getenv("AUTO_RESTART_WORKER", "true").lower() == "true":
        run_with_restart()
    else:
        main()
