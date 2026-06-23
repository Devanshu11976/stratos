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
    try:
        # Check Redis connection
        if not redis_health_check():
            print("ERROR: Redis connection failed", file=sys.stderr)
            return False
        
        # Check queue for stuck jobs
        redis_conn = redis_manager.get_connection()
        queue = Queue("default", connection=redis_conn)
        
        # Get queue statistics
        queued_jobs = queue.count
        started_job_registry = queue.started_job_registry
        
        # Check for stuck jobs (jobs in started registry for > 30 minutes)
        stuck_count = 0
        now = datetime.utcnow()
        for job_id in started_job_registry.get_job_ids():
            job = queue.fetch_job(job_id)
            if job and job.started_at:
                duration = (now - job.started_at).total_seconds() / 60
                if duration > 30:  # 30 minutes threshold
                    stuck_count += 1
        
        # Health is OK if no stuck jobs
        if stuck_count > 0:
            print(f"WARNING: Found {stuck_count} stuck jobs", file=sys.stderr)
            return False
        
        print(f"OK: Worker healthy - queued: {queued_jobs}, started: {len(started_job_registry)}")
        return True
        
    except Exception as e:
        print(f"ERROR: Health check failed: {e}", file=sys.stderr)
        return False


if __name__ == "__main__":
    # Exit with 0 if healthy, 1 if unhealthy
    healthy = check_worker_health()
    sys.exit(0 if healthy else 1)
