#!/usr/bin/env python3
"""
Railway worker entry point - starts RQ worker for background task processing
"""
import os
import sys
import time
from redis import Redis
from rq import Worker, Queue
from app.config.settings import settings

# TCP keepalive constants
TCP_KEEPIDLE = 0x4  # Seconds before sending first keepalive
TCP_KEEPINTVL = 0x5  # Seconds between keepalive probes
TCP_KEEPCNT = 0x6    # Number of failed probes before dropping

def main():
    """Start RQ worker to process background tasks"""
    # Create Redis connection with reconnection logic
    max_retries = 5
    redis_conn = None
    for attempt in range(max_retries):
        try:
            redis_conn = Redis.from_url(
                settings.REDIS_URL,
                socket_keepalive=True,
                socket_keepalive_options={
                    TCP_KEEPIDLE: 10,
                    TCP_KEEPINTVL: 5,
                    TCP_KEEPCNT: 3
                },
                socket_timeout=60,
                socket_connect_timeout=30,
                health_check_interval=15,
                retry_on_timeout=True,
                decode_responses=False
            )
            # Test connection
            redis_conn.ping()
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
    
    worker.work(with_scheduler=True)

def run_with_restart():
    """Run worker with automatic restart on exit"""
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
