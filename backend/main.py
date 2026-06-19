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
            "phone_regex": r"^\d{10}$",
            "date_format": "DD/MM/YYYY",
            "valid_payment_modes": ["UPI", "CARD", "NETBANKING", "WALLET", "CASH"],
            "valid_currencies": ["INR"],
            "min_quantity": 1,
            "max_quantity": 1000,
            "min_amount": 0.01,
            "max_amount": 1000000.0,
            "allow_future_dates": False,
            "required_fields": ["order_id", "customer_name", "email", "phone", "amount", "country_code", "payment_mode"],
        },
        {
            "country_code": "SG",
            "country_name": "Singapore",
            "phone_regex": r"^\d{8}$",
            "date_format": "DD-MM-YYYY",
            "valid_payment_modes": ["PAYNOW", "NETS", "GRABPAY", "CARD", "CASH"],
            "valid_currencies": ["SGD"],
            "min_quantity": 1,
            "max_quantity": 1000,
            "min_amount": 0.01,
            "max_amount": 1000000.0,
            "allow_future_dates": False,
            "required_fields": ["order_id", "customer_name", "email", "phone", "amount", "country_code", "payment_mode"],
        },
        {
            "country_code": "US",
            "country_name": "USA",
            "phone_regex": r"^\d{10}$",
            "date_format": "MM/DD/YYYY",
            "valid_payment_modes": ["CARD", "PAYPAL", "APPLE_PAY", "GOOGLE_PAY", "CASH"],
            "valid_currencies": ["USD"],
            "min_quantity": 1,
            "max_quantity": 1000,
            "min_amount": 0.01,
            "max_amount": 1000000.0,
            "allow_future_dates": False,
            "required_fields": ["order_id", "customer_name", "email", "phone", "amount", "country_code", "payment_mode"],
        },
        {
            "country_code": "DE",
            "country_name": "Germany",
            "phone_regex": r"^\d{8,11}$",
            "date_format": "DD.MM.YYYY",
            "valid_payment_modes": ["CARD", "SEPA", "GIROPAY", "PAYPAL", "CASH"],
            "valid_currencies": ["EUR"],
            "min_quantity": 1,
            "max_quantity": 1000,
            "min_amount": 0.01,
            "max_amount": 1000000.0,
            "allow_future_dates": False,
            "required_fields": ["order_id", "customer_name", "email", "phone", "amount", "country_code", "payment_mode"],
        },
        {
            "country_code": "GB",
            "country_name": "United Kingdom",
            "phone_regex": r"^\d{10,11}$",
            "date_format": "DD/MM/YYYY",
            "valid_payment_modes": ["CARD", "BACS", "FASTER_PAYMENTS", "PAYPAL", "CASH"],
            "valid_currencies": ["GBP"],
            "min_quantity": 1,
            "max_quantity": 1000,
            "min_amount": 0.01,
            "max_amount": 1000000.0,
            "allow_future_dates": False,
            "required_fields": ["order_id", "customer_name", "email", "phone", "amount", "country_code", "payment_mode"],
        },
        {
            "country_code": "AU",
            "country_name": "Australia",
            "phone_regex": r"^\d{8,12}$",
            "date_format": "DD/MM/YYYY",
            "valid_payment_modes": ["CARD", "BPAY", "PAYID", "CASH", "PAYPAL"],
            "valid_currencies": ["AUD"],
            "min_quantity": 1,
            "max_quantity": 1000,
            "min_amount": 0.01,
            "max_amount": 1000000.0,
            "allow_future_dates": False,
            "required_fields": ["order_id", "customer_name", "email", "phone", "amount", "country_code", "payment_mode"],
        },
        {
            "country_code": "AE",
            "country_name": "United Arab Emirates",
            "phone_regex": r"^\d{9}$",
            "date_format": "DD/MM/YYYY",
            "valid_payment_modes": ["CARD", "CASH"],
            "valid_currencies": ["AED"],
            "min_quantity": 1,
            "max_quantity": 1000,
            "min_amount": 0.01,
            "max_amount": 1000000.0,
            "allow_future_dates": False,
            "required_fields": ["order_id", "customer_name", "email", "phone", "amount", "country_code", "payment_mode"],
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
                    valid_currencies=rule_data.get("valid_currencies"),
                    min_quantity=rule_data.get("min_quantity", 1),
                    max_quantity=rule_data.get("max_quantity"),
                    min_amount=rule_data.get("min_amount"),
                    max_amount=rule_data.get("max_amount"),
                    allow_future_dates=rule_data.get("allow_future_dates", False),
                    required_fields=rule_data.get("required_fields"),
                    email_domain_whitelist=rule_data.get("email_domain_whitelist"),
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
