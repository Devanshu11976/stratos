# Auto-Recovery Mechanisms for Server and Worker

## Problem
Server and worker going down due to inactivity, causing jobs to get stuck in queue waiting for worker or stuck in Redis.

## Solution
Implemented multi-layered auto-recovery mechanisms to detect and automatically restart services when they fail or become unresponsive.

## Changes Made

### 1. Updated Procfile
**File:** `backend/Procfile`

**Change:** Updated worker command to use `start_worker.py` instead of `rq.cli`

**Before:**
```yaml
worker: python -m rq.cli worker --url $REDIS_URL default
```

**After:**
```yaml
worker: python start_worker.py
```

**Benefit:** Uses custom worker script with built-in auto-restart logic and health monitoring.

### 2. Enhanced Health Check Endpoints
**File:** `backend/main.py`

**Added:** Two health check endpoints

#### `/api/health` - Basic Health Check
- Checks Redis connection status
- Returns service status and Redis connectivity
- Used for basic API health monitoring

#### `/api/health/queue` - Queue Health Check
- Checks Redis connection
- Monitors queue statistics (queued, started, finished, failed)
- Detects stuck jobs (jobs running > 30 minutes)
- Returns detailed queue health status

**Response Example:**
```json
{
  "status": "healthy",
  "queue": {
    "queued": 5,
    "started": 2,
    "finished": 150,
    "failed": 3
  },
  "stuck_jobs": [],
  "redis": "connected"
}
```

### 3. Worker Heartbeat with Stuck Job Detection
**File:** `backend/start_worker.py`

**Enhanced:** Heartbeat function now monitors both Redis connection and stuck jobs

**Features:**
- Checks Redis connection every 20 seconds
- Monitors started job registry for jobs running > 30 minutes
- Automatically triggers worker restart if:
  - Redis connection fails
  - Stuck jobs detected
- Logs detailed information about detected issues

**Logic:**
```python
def heartbeat():
    while not stop_event.is_set():
        # Check Redis connection
        if not redis_health_check():
            raise ConnectionError("Redis health check failed")
        
        # Check for stuck jobs
        for job_id in started_job_registry.get_job_ids():
            job = queue.fetch_job(job_id)
            if job.started_at and duration > 30 minutes:
                stuck_count += 1
        
        if stuck_count > 0:
            # Trigger worker restart
            os._exit(1)
```

### 4. Standalone Worker Health Check Script
**File:** `backend/worker_health_check.py` (NEW)

**Purpose:** Standalone health check for worker deployments without web server

**Features:**
- Checks Redis connection
- Monitors queue for stuck jobs
- Returns exit code 0 (healthy) or 1 (unhealthy)
- Can be used by deployment platforms for health monitoring

**Usage:**
```bash
python worker_health_check.py
# Exit code 0 = healthy
# Exit code 1 = unhealthy
```

### 5. Docker Health Check
**File:** `backend/Dockerfile`

**Added:** HEALTHCHECK instruction

**Configuration:**
- Interval: 30 seconds
- Timeout: 10 seconds
- Retries: 3
- Start period: 40 seconds

**Logic:**
```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=40s \
    CMD sh -c "if [ \"$RQ_WORKER\" = \"true\" ]; then python worker_health_check.py; else curl -f http://localhost:8000/api/health || exit 1; fi"
```

**Benefit:** Docker automatically restarts container if health check fails 3 times in a row.

### 6. Render Worker Health Check
**File:** `render.yaml`

**Added:** Health check path to worker service

**Change:**
```yaml
- type: worker
  name: xeno-worker
  healthCheckPath: /api/health/queue
```

**Note:** This requires the worker to run a web server. Since workers don't currently run a web server, the Docker HEALTHCHECK is more appropriate for worker deployments.

### 7. Railway Restart Policy
**File:** `backend/railway.toml`

**Already Configured:**
```toml
[deploy]
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 10
```

**Benefit:** Railway automatically restarts service on failure up to 10 times.

## Auto-Recovery Layers

### Layer 1: Application-Level (Fastest)
- **Worker heartbeat** (every 20 seconds)
- Detects Redis connection loss
- Detects stuck jobs (> 30 minutes)
- Triggers immediate worker restart via `AUTO_RESTART_WORKER` loop

### Layer 2: Container-Level (Medium)
- **Docker HEALTHCHECK** (every 30 seconds)
- Runs health check script
- Docker restarts container after 3 consecutive failures
- Works for both API and worker services

### Layer 3: Platform-Level (Slowest)
- **Render/Railway restart policies**
- Platform monitors service health
- Automatically restarts on failure
- Railway: Up to 10 retries
- Render: Automatic based on health checks

## Stuck Job Detection

**Definition:** A job is considered "stuck" if it's in the "started" registry for more than 30 minutes.

**Detection:**
```python
if job.started_at and (now - job.started_at) > timedelta(minutes=30):
    job is stuck
```

**Action:** Worker automatically restarts, which releases stuck jobs back to queue for reprocessing.

## Configuration

### Environment Variables

**AUTO_RESTART_WORKER** (default: true)
- Enables/disables worker auto-restart on exit
- Set to `false` to disable auto-restart for debugging

**RQ_WORKER** (default: false)
- Indicates this is a worker deployment
- Used by Dockerfile to select appropriate startup command

### Health Check Thresholds

**Stuck Job Threshold:** 30 minutes
- Jobs running longer than this are considered stuck
- Can be adjusted in `start_worker.py` and `worker_health_check.py`

**Heartbeat Interval:** 20 seconds
- How often worker checks Redis and queue health
- Can be adjusted in `start_worker.py`

**Docker Health Check:** Every 30 seconds
- Container-level health monitoring
- Configured in Dockerfile

## Testing

### Test Health Check Endpoints
```bash
# API health check
curl http://localhost:8000/api/health

# Queue health check
curl http://localhost:8000/api/health/queue
```

### Test Worker Health Check Script
```bash
cd backend
python worker_health_check.py
echo $?  # Should be 0 if healthy, 1 if unhealthy
```

### Test Auto-Restart
1. Stop Redis server
2. Worker should detect connection loss within 20 seconds
3. Worker should restart automatically
4. Restart Redis
5. Worker should reconnect and resume processing

### Test Stuck Job Detection
1. Manually move a job to "started" registry
2. Set its `started_at` to > 30 minutes ago
3. Worker should detect stuck job within 20 seconds
4. Worker should restart automatically

## Monitoring

### Logs to Monitor

**Worker Logs:**
- `Heartbeat: Redis connection lost` - Connection failure detected
- `Heartbeat: Found stuck job {job_id} running for {duration} minutes` - Stuck job detected
- `Worker exited with error: {error}` - Worker crashed
- `Restarting in 5 seconds...` - Auto-restart triggered

**Docker Logs:**
- Container restart events
- Health check failures

**Platform Logs:**
- Render/Railway service restart events
- Deployment health status

### Metrics to Track

- Worker uptime
- Redis connection failures
- Stuck job count
- Worker restart frequency
- Queue backlog size

## Expected Behavior

### Normal Operation
- Worker processes jobs normally
- Heartbeat checks pass every 20 seconds
- Docker health checks pass every 30 seconds
- No automatic restarts

### Redis Connection Loss
1. Worker heartbeat detects connection loss within 20 seconds
2. Worker exits with error
3. Auto-restart loop restarts worker after 5 seconds
4. Worker reconnects to Redis
5. Processing resumes

### Stuck Job Detected
1. Worker heartbeat detects job running > 30 minutes
2. Worker exits to release stuck job
3. Auto-restart loop restarts worker after 5 seconds
4. Stuck job returns to queue
5. Job reprocessed by new worker instance

### Container Crash
1. Docker health check fails 3 times in a row
2. Docker automatically restarts container
3. Worker starts fresh
4. Processing resumes

## Files Modified

1. `backend/Procfile` - Updated worker command
2. `backend/main.py` - Added health check endpoints
3. `backend/start_worker.py` - Enhanced heartbeat with stuck job detection
4. `backend/worker_health_check.py` - NEW standalone health check script
5. `backend/Dockerfile` - Added HEALTHCHECK instruction
6. `render.yaml` - Added health check path to worker

## Benefits

1. **Automatic Recovery:** Services restart automatically without manual intervention
2. **Multi-Layer Protection:** Three layers of detection and recovery
3. **Stuck Job Prevention:** Detects and resolves stuck jobs automatically
4. **Reduced Downtime:** Fast detection (20-30 seconds) and recovery
5. **Better Monitoring:** Health check endpoints provide visibility
6. **Platform Integration:** Works with Docker, Render, and Railway

## Next Steps

- Monitor logs for restart events
- Adjust thresholds based on actual job processing times
- Set up alerts for frequent restarts
- Consider implementing job timeout at the task level
- Add metrics dashboard for monitoring
