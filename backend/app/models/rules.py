from __future__ import annotations

import uuid
from sqlalchemy import String, Boolean, Integer, Index, text, Float
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.models.database import Base


class CountryRules(Base):
    __tablename__ = "country_rules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    country_code: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    country_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone_regex: Mapped[str] = mapped_column(String(255), nullable=False)
    date_format: Mapped[str] = mapped_column(String(50), nullable=False)
    # JSON array of accepted payment modes e.g. ["UPI","CARD","NETBANKING"].
    # NULL = permissive: all modes accepted (safe default for new countries).
    valid_payment_modes: Mapped[list | None] = mapped_column(
        JSONB, nullable=True, default=None
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Enhanced validation configuration
    # Allowed currencies for this country (e.g., ["INR", "USD"])
    valid_currencies: Mapped[list | None] = mapped_column(
        JSONB, nullable=True, default=None
    )
    # Minimum and maximum amount limits
    min_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Minimum and maximum quantity limits
    min_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True, default=1)
    max_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Whether to allow future transaction dates
    allow_future_dates: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Required fields for this country (e.g., ["email", "customer_name"])
    required_fields: Mapped[list | None] = mapped_column(
        JSONB, nullable=True, default=None
    )
    # Email domain whitelist (e.g., ["gmail.com", "yahoo.com"])
    email_domain_whitelist: Mapped[list | None] = mapped_column(
        JSONB, nullable=True, default=None
    )

    __table_args__ = (
        Index(
            "uq_country_rules_active_code",
            "country_code",
            unique=True,
            postgresql_where=text("is_active = TRUE"),
        ),
    )
