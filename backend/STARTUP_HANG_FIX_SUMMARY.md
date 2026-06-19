# FastAPI/Uvicorn Startup Hang Fix Summary

## Problem
Render deploy hangs at FastAPI/Uvicorn application startup after successfully completing Alembic migration (~8 seconds). Logs show:
```
10:50:56 AM  INFO [alembic.runtime.migration] Will assume transactional DDL.
10:51:04 AM  INFO: Started server process [28]
10:51:04 AM  INFO: Waiting for application startup.
[no further log lines]
```

The "Waiting for application startup" message indicates Uvicorn is waiting for startup event handlers to complete, but no "Application startup complete" message appears, indicating something inside the startup handler is hanging.

## Root Cause
The startup handler `on_startup()` in `main.py` calls `seed_country_rules()`, which uses `session_scope()` to connect to the database. The database connection was hanging during startup, similar to the earlier Alembic issue, but at a different point in the application lifecycle.

Two issues identified:
1. **Database engine creation at module import time**: The SQLAlchemy engine is created when `app/config/db.py` is imported, before the startup handler runs. This engine creation had no connect timeout.
2. **Startup handler database operations**: The `seed_country_rules()` function uses database connections without any timeout protection.

## Files Modified

### 1. `backend/main.py`
**Lines 121-138 (on_startup function):**
```python
async def on_startup() -> None:
    import logging
    import asyncio
    logger = logging.getLogger("xeno.startup")
    logger.info("Starting application startup sequence...")
    
    try:
        # Add timeout to prevent indefinite hangs during startup
        await asyncio.wait_for(seed_country_rules(), timeout=10.0)
        logger.info("Country rules seeded successfully")
    except asyncio.TimeoutError:
        logger.error("Startup timeout: seed_country_rules() took longer than 10 seconds")
        # Continue startup even if seeding fails - don't block the entire app
    except Exception as e:
        logger.error(f"Startup error in seed_country_rules(): {e}")
        # Continue startup even if seeding fails - don't block the entire app
    
    logger.info("Application startup complete")
```

**Changes:**
- Added logging to track startup progress
- Added 10-second timeout to `seed_country_rules()` call
- Changed error handling to continue startup even if seeding fails (don't block entire app)
- Added explicit "Application startup complete" log message

### 2. `backend/app/config/db.py`
**Lines 26-35 (engine creation):**
```python
engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=settings.db_echo,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=settings.db_pool_timeout,
    pool_pre_ping=True,
    future=True,
    connect_args={"connect_timeout": 10},  # Fail fast on connection issues
)
```

**Changes:**
- Added `connect_args={"connect_timeout": 10}` to fail fast on connection issues during engine creation

## Startup Operations Identified
1. **Module import time**: Database engine creation (now has connect_timeout)
2. **Startup handler**: `seed_country_rules()` function (now has 10-second timeout)

## Fix Applied
1. **Added connect_timeout to database engine**: Prevents indefinite hangs during module import when the engine is created
2. **Added timeout to startup handler**: 10-second timeout on `seed_country_rules()` to prevent indefinite hangs
3. **Added logging**: Provides visibility into startup progress and identifies exactly where hang occurs
4. **Graceful degradation**: Startup continues even if country rules seeding fails, preventing the entire app from being blocked

## Expected Results
Next deploy should:
1. Complete Alembic migration in ~8 seconds (already confirmed working)
2. Reach "INFO: Application startup complete." within a few seconds
3. Health check at `/api/health` should return successfully
4. If database connection fails during startup, app should fail fast with clear error message instead of hanging

## Verification Required
Deploy and confirm:
- Logs show "Starting application startup sequence..."
- Logs show "Application startup complete" within 10 seconds
- Health check at `/api/health` returns `{"status": "healthy", "service": "Xeno Backend"}`
- If timeout occurs, logs show clear error message indicating which operation timed out

## Scope
This fix addresses the FastAPI/Uvicorn startup sequence only. Alembic migration code was not modified as it's confirmed working correctly.
