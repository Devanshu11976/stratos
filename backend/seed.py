"""Run once to insert default country validation rules."""
import asyncio
from sqlalchemy import select
from app.config.db import async_session_factory
from app.models.rules import CountryRules

RULES = [
    {"country_code": "IN", "country_name": "India",       "phone_regex": r"^\d{10}$",   "date_format": "DD/MM/YYYY", "valid_payment_modes": ["UPI", "CARD", "NETBANKING", "WALLET", "CASH"], "valid_currencies": ["INR"], "min_quantity": 1, "max_quantity": 1000, "min_amount": 0.01, "max_amount": 1000000.0, "allow_future_dates": False, "required_fields": ["order_id", "customer_name", "email", "phone", "amount", "country_code", "payment_mode"]},
    {"country_code": "SG", "country_name": "Singapore",   "phone_regex": r"^\d{8}$",    "date_format": "DD-MM-YYYY", "valid_payment_modes": ["PAYNOW", "NETS", "GRABPAY", "CARD", "CASH"], "valid_currencies": ["SGD"], "min_quantity": 1, "max_quantity": 1000, "min_amount": 0.01, "max_amount": 1000000.0, "allow_future_dates": False, "required_fields": ["order_id", "customer_name", "email", "phone", "amount", "country_code", "payment_mode"]},
    {"country_code": "US", "country_name": "USA",         "phone_regex": r"^\d{10}$",     "date_format": "MM/DD/YYYY", "valid_payment_modes": ["CARD", "PAYPAL", "APPLE_PAY", "GOOGLE_PAY", "CASH"], "valid_currencies": ["USD"], "min_quantity": 1, "max_quantity": 1000, "min_amount": 0.01, "max_amount": 1000000.0, "allow_future_dates": False, "required_fields": ["order_id", "customer_name", "email", "phone", "amount", "country_code", "payment_mode"]},
    {"country_code": "DE", "country_name": "Germany",     "phone_regex": r"^\d{8,11}$",     "date_format": "DD.MM.YYYY", "valid_payment_modes": ["CARD", "SEPA", "GIROPAY", "PAYPAL", "CASH"], "valid_currencies": ["EUR"], "min_quantity": 1, "max_quantity": 1000, "min_amount": 0.01, "max_amount": 1000000.0, "allow_future_dates": False, "required_fields": ["order_id", "customer_name", "email", "phone", "amount", "country_code", "payment_mode"]},
    {"country_code": "GB", "country_name": "UK",          "phone_regex": r"^\d{10,11}$",        "date_format": "DD/MM/YYYY", "valid_payment_modes": ["CARD", "BACS", "FASTER_PAYMENTS", "PAYPAL", "CASH"], "valid_currencies": ["GBP"], "min_quantity": 1, "max_quantity": 1000, "min_amount": 0.01, "max_amount": 1000000.0, "allow_future_dates": False, "required_fields": ["order_id", "customer_name", "email", "phone", "amount", "country_code", "payment_mode"]},
    {"country_code": "AU", "country_name": "Australia",   "phone_regex": r"^\d{8,12}$",    "date_format": "DD/MM/YYYY", "valid_payment_modes": ["CARD", "BPAY", "PAYID", "CASH", "PAYPAL"], "valid_currencies": ["AUD"], "min_quantity": 1, "max_quantity": 1000, "min_amount": 0.01, "max_amount": 1000000.0, "allow_future_dates": False, "required_fields": ["order_id", "customer_name", "email", "phone", "amount", "country_code", "payment_mode"]},
    {"country_code": "AE", "country_name": "United Arab Emirates",   "phone_regex": r"^\d{9}$",    "date_format": "DD/MM/YYYY", "valid_payment_modes": ["CARD", "CASH"], "valid_currencies": ["AED"], "min_quantity": 1, "max_quantity": 1000, "min_amount": 0.01, "max_amount": 1000000.0, "allow_future_dates": False, "required_fields": ["order_id", "customer_name", "email", "phone", "amount", "country_code", "payment_mode"]},
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
                obj.valid_payment_modes = r.get("valid_payment_modes")
                obj.valid_currencies = r.get("valid_currencies")
                obj.min_quantity = r.get("min_quantity", 1)
                obj.max_quantity = r.get("max_quantity")
                obj.min_amount = r.get("min_amount")
                obj.max_amount = r.get("max_amount")
                obj.allow_future_dates = r.get("allow_future_dates", False)
                obj.required_fields = r.get("required_fields")
                obj.email_domain_whitelist = r.get("email_domain_whitelist")
                print(f"  * {r['country_code']} (updated)")
        await session.commit()
    print("Done.")

asyncio.run(seed())
