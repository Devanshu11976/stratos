import os
from dotenv import load_dotenv
from litestar import Litestar, get
from litestar.di import Provide
from litestar.openapi import OpenAPIConfig, OpenAPIController
from litestar.config.cors import CORSConfig

from sqlalchemy.ext.asyncio import AsyncSession
from app.api import UploadController, RulesController
from app.config.db import get_db_session, close_db_connections

load_dotenv()


class SpecController(OpenAPIController):
    path = "/api/docs"


@get("/api/health")
async def health_check() -> dict[str, str]:
    return {"status": "healthy", "service": "Xeno Backend"}


@get("/api/stats")
async def get_stats(session: AsyncSession) -> dict:
    """Live platform stats for the Hero section badges."""
    from sqlalchemy import func, select
    from app.models.jobs import ProcessingJobs
    from app.models.rules import CountryRules
    from app.models.ai import AIReports

    active = (await session.execute(
        select(func.count()).where(ProcessingJobs.status.in_(["queued", "processing"]))
    )).scalar() or 0
    rules = (await session.execute(
        select(func.count()).where(CountryRules.is_active == True)
    )).scalar() or 0
    records = (await session.execute(
        select(func.coalesce(func.sum(ProcessingJobs.total_records), 0))
        .where(ProcessingJobs.status == "completed")
    )).scalar() or 0
    avg_score = (await session.execute(
        select(func.avg(AIReports.quality_score))
    )).scalar()

    return {
        "active_jobs": int(active),
        "country_rule_count": int(rules),
        "processed_records": int(records),
        "avg_quality_score": round(float(avg_score), 2) if avg_score else 0.0,
    }


async def seed_country_rules() -> None:
    """Insert default country rules on startup if they don't exist yet."""
    from app.config.db import session_scope
    from app.repositories.rules import CountryRulesRepository
    from app.models.rules import CountryRules

    DEFAULT_RULES = [
        {
            "country_code": "IN",
            "country_name": "India",
            "phone_regex": r"^\+91[6-9]\d{9}$",
            "date_format": "DD/MM/YYYY",
            "valid_payment_modes": ["UPI", "CARD", "NETBANKING", "CASH", "WALLET"],
        },
        {
            "country_code": "SG",
            "country_name": "Singapore",
            "phone_regex": r"^\+65[689]\d{7}$",
            "date_format": "DD-MM-YYYY",
            "valid_payment_modes": ["CARD", "PAYNOW", "NETS", "CASH", "GRABPAY"],
        },
        {
            "country_code": "US",
            "country_name": "USA",
            "phone_regex": r"^\+1[2-9]\d{2}[2-9]\d{6}$",
            "date_format": "MM/DD/YYYY",
            "valid_payment_modes": ["CARD", "ACH", "WIRE", "PAYPAL", "CASH"],
        },
        {
            "country_code": "DE",
            "country_name": "Germany",
            "phone_regex": r"^\+49[1-9]\d{6,12}$",
            "date_format": "DD.MM.YYYY",
            "valid_payment_modes": ["CARD", "SEPA", "GIROPAY", "PAYPAL", "CASH"],
        },
        {
            "country_code": "GB",
            "country_name": "United Kingdom",
            "phone_regex": r"^\+44[1-9]\d{9}$",
            "date_format": "DD/MM/YYYY",
            "valid_payment_modes": ["CARD", "BACS", "FASTER_PAYMENTS", "PAYPAL", "CASH"],
        },
        {
            "country_code": "AU",
            "country_name": "Australia",
            "phone_regex": r"^\+61[2-9]\d{8}$",
            "date_format": "DD/MM/YYYY",
            "valid_payment_modes": ["CARD", "BPAY", "PAYID", "CASH", "PAYPAL"],
        },
    ]

    async with session_scope() as session:
        repo = CountryRulesRepository(session)
        for rule_data in DEFAULT_RULES:
            existing = await repo.get_by_code(rule_data["country_code"])
            if not existing:
                rule = CountryRules(
                    country_code=rule_data["country_code"],
                    country_name=rule_data["country_name"],
                    phone_regex=rule_data["phone_regex"],
                    date_format=rule_data["date_format"],
                    valid_payment_modes=rule_data.get("valid_payment_modes"),
                    is_active=True,
                )
                await repo.create(rule)


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


cors_config = CORSConfig(
    allow_origins=["*"],
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

app = Litestar(
    route_handlers=[
        health_check,
        get_stats,
        UploadController,
        RulesController,
    ],
    cors_config=cors_config,
    dependencies={"session": Provide(get_db_session)},
    on_shutdown=[close_db_connections],
    on_startup=[on_startup],
    openapi_config=OpenAPIConfig(
        title="Xeno Data Intelligence Hub API",
        version="1.0.0",
        openapi_controller=SpecController,
    ),
)

if __name__ == "__main__":
    import uvicorn
    debug = os.getenv("DEBUG", "false").lower() == "true"
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=debug)
