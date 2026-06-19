"""Core validation framework with error codes and severity levels."""

from enum import Enum
from dataclasses import dataclass
from typing import Optional


class ErrorSeverity(str, Enum):
    """Error severity levels."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ErrorCode(str, Enum):
    """Standardized error codes for validation."""
    # Schema validation
    MISSING_REQUIRED_COLUMN = "MISSING_REQUIRED_COLUMN"
    DUPLICATE_COLUMN_NAME = "DUPLICATE_COLUMN_NAME"
    INVALID_DATA_TYPE = "INVALID_DATA_TYPE"
    EMPTY_FILE = "EMPTY_FILE"
    CORRUPTED_FILE = "CORRUPTED_FILE"
    UNSUPPORTED_FILE_TYPE = "UNSUPPORTED_FILE_TYPE"
    
    # Phone validation
    INVALID_PHONE = "INVALID_PHONE"
    PHONE_TOO_SHORT = "PHONE_TOO_SHORT"
    PHONE_TOO_LONG = "PHONE_TOO_LONG"
    
    # Email validation
    INVALID_EMAIL = "INVALID_EMAIL"
    MISSING_EMAIL = "MISSING_EMAIL"
    
    # Name validation
    INVALID_NAME = "INVALID_NAME"
    NAME_TOO_SHORT = "NAME_TOO_SHORT"
    NAME_TOO_LONG = "NAME_TOO_LONG"
    
    # Order ID validation
    DUPLICATE_ORDER_ID = "DUPLICATE_ORDER_ID"
    INVALID_ORDER_ID = "INVALID_ORDER_ID"
    
    # Product validation
    INVALID_PRODUCT = "INVALID_PRODUCT"
    MISSING_PRODUCT = "MISSING_PRODUCT"
    
    # Quantity validation
    INVALID_QUANTITY = "INVALID_QUANTITY"
    QUANTITY_TOO_LOW = "QUANTITY_TOO_LOW"
    QUANTITY_TOO_HIGH = "QUANTITY_TOO_HIGH"
    
    # Amount validation
    INVALID_AMOUNT = "INVALID_AMOUNT"
    NEGATIVE_AMOUNT = "NEGATIVE_AMOUNT"
    AMOUNT_TOO_LOW = "AMOUNT_TOO_LOW"
    AMOUNT_TOO_HIGH = "AMOUNT_TOO_HIGH"
    
    # Currency validation
    INVALID_CURRENCY = "INVALID_CURRENCY"
    
    # Country validation
    INVALID_COUNTRY = "INVALID_COUNTRY"
    UNSUPPORTED_COUNTRY = "UNSUPPORTED_COUNTRY"
    
    # Date validation
    INVALID_DATE = "INVALID_DATE"
    INVALID_DATE_FORMAT = "INVALID_DATE_FORMAT"
    FUTURE_DATE = "FUTURE_DATE"
    
    # Time validation
    INVALID_TIME = "INVALID_TIME"
    
    # Payment mode validation
    INVALID_PAYMENT_MODE = "INVALID_PAYMENT_MODE"
    
    # Duplicate detection
    DUPLICATE_RECORD = "DUPLICATE_RECORD"
    
    # Missing value validation
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    
    # Data integrity
    NEGATIVE_QUANTITY = "NEGATIVE_QUANTITY"
    NEGATIVE_PRICE = "NEGATIVE_PRICE"
    BLANK_MANDATORY_VALUE = "BLANK_MANDATORY_VALUE"
    MALFORMED_RECORD = "MALFORMED_RECORD"
    INVALID_ENUM_VALUE = "INVALID_ENUM_VALUE"


@dataclass
class ValidationError:
    """Standard validation error structure."""
    row_number: int
    field: str
    error_code: ErrorCode
    message: str
    severity: ErrorSeverity = ErrorSeverity.ERROR
    
    def to_dict(self) -> dict:
        """Convert to dictionary format."""
        return {
            "row_number": self.row_number,
            "field": self.field,
            "error_code": self.error_code.value,
            "message": self.message,
            "severity": self.severity.value
        }


@dataclass
class ValidationResult:
    """Result of a validation operation."""
    is_valid: bool
    errors: list[ValidationError]
    warnings: list[ValidationError]
    
    def add_error(self, error: ValidationError) -> None:
        """Add an error to the result."""
        self.errors.append(error)
        self.is_valid = False
    
    def add_warning(self, warning: ValidationError) -> None:
        """Add a warning to the result."""
        self.warnings.append(warning)
    
    def get_all_issues(self) -> list[ValidationError]:
        """Get all errors and warnings."""
        return self.errors + self.warnings
    
    def to_summary(self) -> dict:
        """Get validation summary."""
        return {
            "is_valid": self.is_valid,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "total_issues": len(self.errors) + len(self.warnings)
        }
