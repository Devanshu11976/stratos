"""Individual field validators for the validation framework."""

import re
from datetime import datetime
from typing import Optional
from app.validators.framework import ValidationError, ErrorCode, ErrorSeverity


class EmailValidator:
    """Email address validation."""
    
    EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    
    @staticmethod
    def validate(email: str, row_number: int, domain_whitelist: Optional[list] = None) -> Optional[ValidationError]:
        """Validate email address format and domain."""
        if not email or not str(email).strip():
            return ValidationError(
                row_number=row_number,
                field="email",
                error_code=ErrorCode.MISSING_EMAIL,
                message="Email address is required",
                severity=ErrorSeverity.ERROR
            )
        
        email = str(email).strip()
        
        # Check for spaces
        if ' ' in email:
            return ValidationError(
                row_number=row_number,
                field="email",
                error_code=ErrorCode.INVALID_EMAIL,
                message="Email address cannot contain spaces",
                severity=ErrorSeverity.ERROR
            )
        
        # Check format
        if not EmailValidator.EMAIL_REGEX.match(email):
            return ValidationError(
                row_number=row_number,
                field="email",
                error_code=ErrorCode.INVALID_EMAIL,
                message=f"Invalid email format: {email}",
                severity=ErrorSeverity.ERROR
            )
        
        # Check domain whitelist if provided
        if domain_whitelist:
            domain = email.split('@')[-1].lower()
            if domain not in [d.lower() for d in domain_whitelist]:
                return ValidationError(
                    row_number=row_number,
                    field="email",
                    error_code=ErrorCode.INVALID_EMAIL,
                    message=f"Email domain '{domain}' is not in the allowed list",
                    severity=ErrorSeverity.ERROR
                )
        
        return None


class NameValidator:
    """Customer name validation."""
    
    @staticmethod
    def validate(name: str, row_number: int) -> Optional[ValidationError]:
        """Validate customer name."""
        if not name or not str(name).strip():
            return ValidationError(
                row_number=row_number,
                field="customer_name",
                error_code=ErrorCode.INVALID_NAME,
                message="Customer name is required",
                severity=ErrorSeverity.ERROR
            )
        
        name = str(name).strip()
        
        # Check minimum length
        if len(name) < 2:
            return ValidationError(
                row_number=row_number,
                field="customer_name",
                error_code=ErrorCode.NAME_TOO_SHORT,
                message=f"Customer name must be at least 2 characters (got {len(name)})",
                severity=ErrorSeverity.ERROR
            )
        
        # Check maximum length
        if len(name) > 100:
            return ValidationError(
                row_number=row_number,
                field="customer_name",
                error_code=ErrorCode.NAME_TOO_LONG,
                message=f"Customer name must not exceed 100 characters (got {len(name)})",
                severity=ErrorSeverity.ERROR
            )
        
        # Check if numeric only
        if name.isdigit():
            return ValidationError(
                row_number=row_number,
                field="customer_name",
                error_code=ErrorCode.INVALID_NAME,
                message="Customer name cannot be numeric only",
                severity=ErrorSeverity.ERROR
            )
        
        # Check if special characters only
        if not re.search(r'[a-zA-Z]', name):
            return ValidationError(
                row_number=row_number,
                field="customer_name",
                error_code=ErrorCode.INVALID_NAME,
                message="Customer name must contain at least one letter",
                severity=ErrorSeverity.ERROR
            )
        
        return None


class TimeValidator:
    """Time validation."""
    
    TIME_FORMATS = ["%H:%M", "%H:%M:%S"]
    
    @staticmethod
    def validate(time_val: str, row_number: int) -> Optional[ValidationError]:
        """Validate time format (HH:MM or HH:MM:SS)."""
        if not time_val or not str(time_val).strip():
            return None  # Time is optional
        
        time_val = str(time_val).strip()
        
        for fmt in TimeValidator.TIME_FORMATS:
            try:
                parsed = datetime.strptime(time_val, fmt)
                # Validate time ranges
                if parsed.hour > 23 or parsed.minute > 59 or parsed.second > 59:
                    return ValidationError(
                        row_number=row_number,
                        field="time",
                        error_code=ErrorCode.INVALID_TIME,
                        message=f"Invalid time value: {time_val}",
                        severity=ErrorSeverity.ERROR
                    )
                return None
            except ValueError:
                continue
        
        return ValidationError(
            row_number=row_number,
            field="time",
            error_code=ErrorCode.INVALID_TIME,
            message=f"Invalid time format: {time_val} (expected HH:MM or HH:MM:SS)",
            severity=ErrorSeverity.ERROR
        )


class CurrencyValidator:
    """Currency validation."""
    
    ALLOWED_CURRENCIES = {"INR", "USD", "SGD", "EUR", "GBP", "AED"}
    
    @staticmethod
    def validate(currency: str, row_number: int, country_currencies: Optional[list] = None) -> Optional[ValidationError]:
        """Validate currency code."""
        if not currency or not str(currency).strip():
            return None  # Currency is optional
        
        currency = str(currency).strip().upper()
        
        # Check against global allowed currencies
        if currency not in CurrencyValidator.ALLOWED_CURRENCIES:
            return ValidationError(
                row_number=row_number,
                field="currency",
                error_code=ErrorCode.INVALID_CURRENCY,
                message=f"Invalid currency: {currency}. Allowed: {', '.join(sorted(CurrencyValidator.ALLOWED_CURRENCIES))}",
                severity=ErrorSeverity.ERROR
            )
        
        # Check against country-specific currencies if provided
        if country_currencies:
            if currency not in [c.upper() for c in country_currencies]:
                return ValidationError(
                    row_number=row_number,
                    field="currency",
                    error_code=ErrorCode.INVALID_CURRENCY,
                    message=f"Currency '{currency}' is not allowed for this country. Allowed: {', '.join(country_currencies)}",
                    severity=ErrorSeverity.ERROR
                )
        
        return None


class CountryValidator:
    """Country code validation."""
    
    SUPPORTED_COUNTRIES = {"IN", "SG", "US", "UK", "AE", "DE", "GB", "AU"}
    
    @staticmethod
    def validate(country: str, row_number: int) -> Optional[ValidationError]:
        """Validate country code."""
        if not country or not str(country).strip():
            return ValidationError(
                row_number=row_number,
                field="country",
                error_code=ErrorCode.INVALID_COUNTRY,
                message="Country code is required",
                severity=ErrorSeverity.ERROR
            )
        
        country = str(country).strip().upper()
        
        # Normalize UK to GB
        if country == "UK":
            country = "GB"
        
        if country not in CountryValidator.SUPPORTED_COUNTRIES:
            return ValidationError(
                row_number=row_number,
                field="country",
                error_code=ErrorCode.UNSUPPORTED_COUNTRY,
                message=f"Unsupported country: {country}. Supported: {', '.join(sorted(CountryValidator.SUPPORTED_COUNTRIES))}",
                severity=ErrorSeverity.ERROR
            )
        
        return None


class QuantityValidator:
    """Quantity validation."""
    
    @staticmethod
    def validate(quantity, row_number: int, min_qty: int = 1, max_qty: Optional[int] = None) -> Optional[ValidationError]:
        """Validate quantity value."""
        if quantity is None or not str(quantity).strip():
            return ValidationError(
                row_number=row_number,
                field="quantity",
                error_code=ErrorCode.MISSING_REQUIRED_FIELD,
                message="Quantity is required",
                severity=ErrorSeverity.ERROR
            )
        
        try:
            qty = float(str(quantity))
        except (ValueError, TypeError):
            return ValidationError(
                row_number=row_number,
                field="quantity",
                error_code=ErrorCode.INVALID_QUANTITY,
                message=f"Invalid quantity value: {quantity}",
                severity=ErrorSeverity.ERROR
            )
        
        # Check for negative
        if qty < 0:
            return ValidationError(
                row_number=row_number,
                field="quantity",
                error_code=ErrorCode.NEGATIVE_QUANTITY,
                message=f"Quantity cannot be negative: {qty}",
                severity=ErrorSeverity.ERROR
            )
        
        # Check minimum
        if qty < min_qty:
            return ValidationError(
                row_number=row_number,
                field="quantity",
                error_code=ErrorCode.QUANTITY_TOO_LOW,
                message=f"Quantity must be at least {min_qty} (got {qty})",
                severity=ErrorSeverity.ERROR
            )
        
        # Check maximum if specified
        if max_qty is not None and qty > max_qty:
            return ValidationError(
                row_number=row_number,
                field="quantity",
                error_code=ErrorCode.QUANTITY_TOO_HIGH,
                message=f"Quantity must not exceed {max_qty} (got {qty})",
                severity=ErrorSeverity.ERROR
            )
        
        return None


class AmountValidator:
    """Transaction amount validation."""
    
    @staticmethod
    def validate(amount, row_number: int, min_amount: float = 0.01, max_amount: Optional[float] = None) -> Optional[ValidationError]:
        """Validate transaction amount."""
        if amount is None or not str(amount).strip():
            return ValidationError(
                row_number=row_number,
                field="amount",
                error_code=ErrorCode.MISSING_REQUIRED_FIELD,
                message="Amount is required",
                severity=ErrorSeverity.ERROR
            )
        
        try:
            amt = float(str(amount))
        except (ValueError, TypeError):
            return ValidationError(
                row_number=row_number,
                field="amount",
                error_code=ErrorCode.INVALID_AMOUNT,
                message=f"Invalid amount value: {amount}",
                severity=ErrorSeverity.ERROR
            )
        
        # Check for zero or negative
        if amt <= 0:
            return ValidationError(
                row_number=row_number,
                field="amount",
                error_code=ErrorCode.NEGATIVE_AMOUNT,
                message=f"Amount must be greater than 0 (got {amt})",
                severity=ErrorSeverity.ERROR
            )
        
        # Check minimum
        if amt < min_amount:
            return ValidationError(
                row_number=row_number,
                field="amount",
                error_code=ErrorCode.AMOUNT_TOO_LOW,
                message=f"Amount must be at least {min_amount} (got {amt})",
                severity=ErrorSeverity.ERROR
            )
        
        # Check maximum if specified
        if max_amount is not None and amt > max_amount:
            return ValidationError(
                row_number=row_number,
                field="amount",
                error_code=ErrorCode.AMOUNT_TOO_HIGH,
                message=f"Amount must not exceed {max_amount} (got {amt})",
                severity=ErrorSeverity.ERROR
            )
        
        return None
