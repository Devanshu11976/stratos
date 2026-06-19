"""Schema validation for CSV/Excel files."""

import polars as pl
from pathlib import Path
from typing import Optional
from app.validators.framework import ValidationError, ErrorCode, ErrorSeverity


class SchemaValidator:
    """Validates file schema and structure."""
    
    REQUIRED_COLUMNS = [
        "order_id", "product_id", "quantity", "amount",
        "phone_number", "payment_mode", "transaction_date"
    ]
    
    OPTIONAL_COLUMNS = [
        "customer_name", "email", "country", "currency",
        "time", "transaction_id", "customer_id"
    ]
    
    SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls"}
    
    @staticmethod
    def validate_file_path(file_path: str) -> Optional[ValidationError]:
        """Validate file exists and has supported extension."""
        path = Path(file_path)
        
        if not path.exists():
            return ValidationError(
                row_number=0,
                field="file",
                error_code=ErrorCode.CORRUPTED_FILE,
                message=f"File does not exist: {file_path}",
                severity=ErrorSeverity.ERROR
            )
        
        if path.suffix.lower() not in SchemaValidator.SUPPORTED_EXTENSIONS:
            return ValidationError(
                row_number=0,
                field="file",
                error_code=ErrorCode.UNSUPPORTED_FILE_TYPE,
                message=f"Unsupported file type: {path.suffix}. Supported: {', '.join(SchemaValidator.SUPPORTED_EXTENSIONS)}",
                severity=ErrorSeverity.ERROR
            )
        
        return None
    
    @staticmethod
    def validate_empty_file(df: pl.DataFrame) -> Optional[ValidationError]:
        """Check if file is empty."""
        if len(df) == 0:
            return ValidationError(
                row_number=0,
                field="file",
                error_code=ErrorCode.EMPTY_FILE,
                message="File contains no data rows",
                severity=ErrorSeverity.ERROR
            )
        return None
    
    @staticmethod
    def validate_columns(df: pl.DataFrame) -> list[ValidationError]:
        """Validate column structure."""
        errors = []
        columns = [col.lower() for col in df.columns]
        
        # Check for duplicate column names
        if len(columns) != len(set(columns)):
            duplicates = [col for col in columns if columns.count(col) > 1]
            errors.append(ValidationError(
                row_number=0,
                field="columns",
                error_code=ErrorCode.DUPLICATE_COLUMN_NAME,
                message=f"Duplicate column names found: {', '.join(set(duplicates))}",
                severity=ErrorSeverity.ERROR
            ))
        
        # Check for required columns
        missing_required = [col for col in SchemaValidator.REQUIRED_COLUMNS if col not in columns]
        if missing_required:
            errors.append(ValidationError(
                row_number=0,
                field="columns",
                error_code=ErrorCode.MISSING_REQUIRED_COLUMN,
                message=f"Missing required columns: {', '.join(missing_required)}",
                severity=ErrorSeverity.ERROR
            ))
        
        return errors
    
    @staticmethod
    def validate_data_types(df: pl.DataFrame) -> list[ValidationError]:
        """Validate data types for key columns."""
        errors = []
        
        # Check if numeric columns can be converted
        numeric_columns = ["quantity", "amount"]
        for col in numeric_columns:
            if col in df.columns:
                try:
                    df[col].cast(pl.Float64)
                except (pl.ComputeError, pl.InvalidOperationError):
                    errors.append(ValidationError(
                        row_number=0,
                        field=col,
                        error_code=ErrorCode.INVALID_DATA_TYPE,
                        message=f"Column '{col}' contains invalid numeric data",
                        severity=ErrorSeverity.ERROR
                    ))
        
        return errors
    
    @staticmethod
    def validate_schema(df: pl.DataFrame, file_path: str) -> list[ValidationError]:
        """Run all schema validations."""
        errors = []
        
        # File validation
        file_error = SchemaValidator.validate_file_path(file_path)
        if file_error:
            errors.append(file_error)
            return errors
        
        # Empty file check
        empty_error = SchemaValidator.validate_empty_file(df)
        if empty_error:
            errors.append(empty_error)
            return errors
        
        # Column validation
        errors.extend(SchemaValidator.validate_columns(df))
        
        # Data type validation
        errors.extend(SchemaValidator.validate_data_types(df))
        
        return errors
