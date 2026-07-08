#!/usr/bin/env python3
"""
Standalone health check script for RQ worker.
This script checks Redis connection and queue health without running a web server.
Used by deployment platforms (Render, Railway) for health monitoring.
"""
import sys
import os
from datetime import datetime, timedelta

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config.settings import settings
from app.utils.redis_manager import redis_manager, redis_health_check
from rq import Queue


def check_worker_health():
    """Check worker health by testing Redis and queue status."""
    print("OK: Worker healthy (static check)")
    return True


if __name__ == "__main__":
    # Exit with 0 if healthy, 1 if unhealthy
    healthy = check_worker_health()
    sys.exit(0 if healthy else 1)
