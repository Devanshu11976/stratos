"""Run once to insert default country validation rules."""
import asyncio
from sqlalchemy import select
from app.config.db import async_session_factory
from app.models.rules import CountryRules

RULES = [
    {"country_code": "IN", "country_name": "India",       "phone_regex": r"^\d{8,12}$",   "date_format": "DD/MM/YYYY", "valid_payment_modes": ["NETBANKING", "UPI", "CARD", "CASH"]},
    {"country_code": "SG", "country_name": "Singapore",   "phone_regex": r"^\d{8,12}$",    "date_format": "DD-MM-YYYY", "valid_payment_modes": ["NETBANKING", "CARD", "CASH", "PAYNOW", "NETS"]},
    {"country_code": "US", "country_name": "USA",         "phone_regex": r"^\d{8,12}$",     "date_format": "MM/DD/YYYY", "valid_payment_modes": ["NETBANKING", "CARD", "ACH", "WIRE", "PAYPAL", "CASH"]},
    {"country_code": "DE", "country_name": "Germany",     "phone_regex": r"^\d{8,12}$",     "date_format": "DD.MM.YYYY", "valid_payment_modes": ["NETBANKING", "CARD", "SEPA", "CASH", "PAYPAL"]},
    {"country_code": "GB", "country_name": "UK",          "phone_regex": r"^\d{8,12}$",        "date_format": "DD/MM/YYYY", "valid_payment_modes": ["CARD", "BACS", "FASTER_PAYMENTS", "PAYPAL", "CASH"]},
    {"country_code": "AU", "country_name": "Australia",   "phone_regex": r"^\d{8,12}$",    "date_format": "DD/MM/YYYY", "valid_payment_modes": ["CARD", "BPAY", "PAYID", "CASH", "PAYPAL"]},
]

async def seed():
    async with async_session_factory() as session:
        for r in RULES:
            existing = await session.execute(
                select(CountryRules).where(CountryRules.country_code == r["country_code"])
            )
            obj = existing.scalars().first()
            if not obj:
                session.add(CountryRules(is_active=True, **r))
                print(f"  + {r['country_code']}")
            else:
                obj.phone_regex = r["phone_regex"]
                obj.date_format = r["date_format"]
                obj.country_name = r["country_name"]
                print(f"  * {r['country_code']} (updated)")
        await session.commit()
    print("Done.")

asyncio.run(seed())
