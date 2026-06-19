import re
import logging
import traceback
import os
import polars as pl
import pandera.polars as pa
from pathlib import Path
from datetime import datetime
from app.services.storage import storage_service
from app.services.report_generator import report_generator
from app.services.ai_insights import ai_insights_generator
from app.validators.rules import build_pandera_schema
from app.validators.framework import ValidationError, ErrorCode, ErrorSeverity
from app.validators.schema_validator import SchemaValidator
from app.validators.field_validators import (
    EmailValidator, NameValidator, TimeValidator, CurrencyValidator,
    CountryValidator, QuantityValidator, AmountValidator
)

logger = logging.getLogger("xeno.validation")

CHUNK_SIZE = 1000

EXPECTED_COLUMNS = [
    "order_id", "product_id", "quantity", "amount",
    "phone_number", "payment_mode", "transaction_date",
]

# Extended required fields based on country rules
EXTENDED_REQUIRED_FIELDS = [
    "customer_name", "email", "country_code"
]

COLUMN_ALIASES = {
    "customer_phone": "phone_number",
    "phone":          "phone_number",
    "contact":        "phone_number",
    "order_date":     "transaction_date",
    "date":           "transaction_date",
    "txn_date":       "transaction_date",
    "transaction_amount": "amount",
    "txn_amount":     "amount",
}

# Permissive fallback used only when no DB rule is found for a country
# Updated to accept local format numbers without country prefix
_FALLBACK_PHONE_REGEX = r"^\d{7,15}$"


def _is_valid_phone(phone_val: str, phone_regex: str) -> bool:
    """Validate phone using the DB-supplied regex exclusively.
    No hardcoded digit-length tables — fully config-driven."""
    return bool(re.match(phone_regex, phone_val.strip()))


def _is_valid_date(date_val: str) -> bool:
    from datetime import datetime
    # Try common date formats, with ISO (YYYY-MM-DD) first as fallback
    date_formats = [
        "%Y-%m-%d",  # ISO format - always accept
        "%d/%m/%Y",  # DD/MM/YYYY
        "%m/%d/%Y",  # MM/DD/YYYY
        "%d-%m-%Y",  # DD-MM-YYYY
        "%d.%m.%Y",  # DD.MM.YYYY
        "%Y/%m/%d",  # YYYY/MM/DD
        "%Y.%m.%d",  # YYYY.MM.DD
    ]
    for fmt in date_formats:
        try:
            parsed = datetime.strptime(date_val, fmt)
            # Additional validation: reject clearly invalid dates
            if parsed.month > 12 or parsed.day > 31:
                return False
            return True
        except ValueError:
            continue
    return False


class ValidationService:
    async def process_dataset(self, job_id: str, file_path: str, country_code: str) -> dict:
        import time
        start_time = time.time()
        # ── 1. Fetch country rules from DB ────────────────────────────────
        from app.config.db import session_scope
        from app.repositories.rules import CountryRulesRepository

        country_rules_map: dict = {}
        fallback_rule = None

        try:
            async with session_scope() as session:
                rules_repo = CountryRulesRepository(session)
                all_rules = await rules_repo.get_all()
                logger.info(f"Job {job_id}: Fetched {len(all_rules)} country rules from DB")
                for r in all_rules:
                    if r.is_active:
                        country_rules_map[r.country_code.upper()] = r
                        country_rules_map[r.country_name.upper()] = r
                # If country_code is AUTO, we have no fallback — every row uses its own column
                if country_code.upper() != "AUTO":
                    fallback_rule = country_rules_map.get(country_code.upper())
                    logger.info(f"Job {job_id}: Using fallback rule for country_code={country_code}: {fallback_rule is not None}")
                else:
                    logger.info(f"Job {job_id}: AUTO mode - will infer country from each row")
        except Exception as e:
            logger.error(f"Failed to fetch country rules: {e}")

        # ── 2. Read file (lazy scan for CSV, eager for XLSX) ──────────────
        file_ext = Path(file_path).suffix.lower()
        logger.info(f"Job {job_id}: Reading file {file_path} with extension {file_ext}")
        try:
            if file_ext == ".csv":
                # Use scan_csv for lazy evaluation — only collect() when needed
                # Force phone_number column to be read as string to prevent scientific notation
                lf = pl.scan_csv(file_path, infer_schema_length=0, dtypes={"phone_number": pl.Utf8, "customer_phone": pl.Utf8})
                df = lf.collect()
            elif file_ext in (".xlsx", ".xls"):
                # fastexcel does not support lazy scan; read fully but streaming-friendly
                # Force phone_number column to be read as string to prevent scientific notation
                df = pl.read_excel(file_path, infer_schema_length=0)
                # Cast phone columns to string to prevent scientific notation
                if "phone_number" in df.columns:
                    df = df.with_columns(pl.col("phone_number").cast(pl.Utf8))
                if "customer_phone" in df.columns:
                    df = df.with_columns(pl.col("customer_phone").cast(pl.Utf8))
            else:
                raise ValueError(f"Unsupported file extension: {file_ext}")
        except Exception as e:
            logger.error(
                f"Failed to read file {file_path}:\n"
                f"Error type: {type(e).__name__}\n"
                f"Error message: {str(e)}\n"
                f"Traceback:\n{traceback.format_exc()}"
            )
            raise

        # Normalise column names
        df = df.rename({c: c.strip().lower().replace(" ", "_") for c in df.columns})
        rename_map = {c: COLUMN_ALIASES[c] for c in df.columns if c in COLUMN_ALIASES}
        if rename_map:
            df = df.rename(rename_map)

        total_records = len(df)
        logger.info(f"Job {job_id}: Loaded {total_records} records from {file_path}")
        logger.info(f"Job {job_id}: DataFrame columns: {df.columns}")
        logger.info(f"Job {job_id}: First 5 rows:\n{df.head(5)}")

        # ── 2.5 Schema validation ───────────────────────────────────────
        schema_errors = SchemaValidator.validate_schema(df, file_path)
        if schema_errors:
            logger.error(f"Job {job_id}: Schema validation failed with {len(schema_errors)} errors")
            for err in schema_errors:
                logger.error(f"  {err.error_code.value}: {err.message}")
            # Return early if schema validation fails
            return {
                "job_id": job_id,
                "status": "failed",
                "total_records": total_records,
                "valid_records": 0,
                "invalid_records": total_records,
                "clean_file_path": None,
                "error_report_path": None,
                "chunk_paths": [],
                "chunk_record_counts": [],
                "error_logs": [e.to_dict() for e in schema_errors],
                "validation_breakdown": {"schema_errors": len(schema_errors)},
                "country_stats": {},
            }

        # ── 3. Pandera structural validation (fast, vectorised) ───────────
        # Use the fallback rule's regex if available; otherwise a permissive default
        pandera_phone_regex = (
            fallback_rule.phone_regex if fallback_rule else r"^\+?\d{7,15}$"
        )
        pandera_date_format = (
            fallback_rule.date_format if fallback_rule else "DD/MM/YYYY"
        )

        logger.info(f"Job {job_id}: Pandera phone_regex={pandera_phone_regex}, date_format={pandera_date_format}")

        pandera_errors: dict[int, list[str]] = {}  # row_idx → [error messages]

        # Only run Pandera on rows that have all required columns present
        pandera_cols = {"order_id", "product_id", "quantity", "amount",
                        "phone_number", "payment_mode", "transaction_date"}
        available_cols = pandera_cols.intersection(set(df.columns))

        logger.info(f"Job {job_id}: Available columns for Pandera: {available_cols}")

        if len(available_cols) == len(pandera_cols):
            schema = build_pandera_schema(pandera_phone_regex, pandera_date_format)
            try:
                schema.validate(df, lazy=True)
            except pa.errors.SchemaErrors as exc:
                # Use native Polars iteration — no pyarrow needed
                logger.info(f"Job {job_id}: Pandera validation failed with {len(exc.failure_cases)} errors")
                for row in exc.failure_cases.iter_rows(named=True):
                    ridx = row.get("index")
                    if ridx is None or ridx < 0:
                        continue
                    col = str(row.get("column") or "")
                    check = str(row.get("check") or "")
                    pandera_errors.setdefault(int(ridx), []).append(f"{col}: {check}")
        else:
            logger.warning(
                f"Job {job_id}: skipping Pandera — missing columns "
                f"{pandera_cols - available_cols}"
            )

        # ── 4. Row-level business-rule validation ─────────────────────────
        error_logs: list[dict] = []
        valid_mask = [True] * total_records

        breakdown: dict = {
            "invalid_phone": 0,
            "invalid_date": 0,
            "invalid_payment_mode": 0,
            "duplicate_order_id": 0,
            "negative_quantity": 0,
            "negative_amount": 0,
            "missing_fields": 0,
            "pandera_schema": 0,
        }
        country_stats: dict[str, dict[str, int]] = {}

        logger.info(f"Job {job_id}: Starting row-level validation for {total_records} rows")

        for row_idx in range(total_records):
            row = df.row(row_idx, named=True)
            row_errors: list[dict] = []

            # Resolve per-row country
            raw_country = str(row.get("country") or "").strip().upper()
            row_rule = country_rules_map.get(raw_country) or fallback_rule

            display_country = (
                row_rule.country_code.upper() if row_rule
                else (raw_country[:2] if raw_country else (country_code.upper() if country_code.upper() != "AUTO" else "XX"))
            )

            country_stats.setdefault(display_country, {"total": 0, "valid": 0, "invalid": 0})
            country_stats[display_country]["total"] += 1

            phone_regex = row_rule.phone_regex if row_rule else _FALLBACK_PHONE_REGEX
            # Load payment modes from DB rule; None = accept all (permissive)
            valid_modes: list[str] | None = (
                [m.upper() for m in row_rule.valid_payment_modes]
                if row_rule and row_rule.valid_payment_modes else None
            )

            # Log phone regex for first row of each country
            if row_idx == 0:
                logger.info(f"Job {job_id}: Country '{display_country}' using phone_regex: {phone_regex}")

            # Surface Pandera failures for this row
            for pe in pandera_errors.get(row_idx, []):
                row_errors.append({
                    "row_number": row_idx + 1,
                    "column_name": pe.split(":")[0] if ":" in pe else "schema",
                    "error_message": f"Schema check failed: {pe}",
                    "error_type": "pandera_schema",
                })
                breakdown["pandera_schema"] += 1

            # Missing fields - check country-specific required fields
            required_fields = EXPECTED_COLUMNS
            if row_rule and row_rule.required_fields:
                required_fields = list(set(required_fields + row_rule.required_fields))
            
            for col in required_fields:
                if col in row:
                    val = row[col]
                    if val is None or (isinstance(val, str) and val.strip() == ""):
                        row_errors.append({
                            "row_number": row_idx + 1,
                            "column_name": col,
                            "error_message": f"Missing required field: {col}",
                            "error_type": "missing_fields",
                        })
                        breakdown["missing_fields"] += 1

            # Email validation
            if row.get("email"):
                email_error = EmailValidator.validate(
                    str(row["email"]),
                    row_idx + 1,
                    row_rule.email_domain_whitelist if row_rule else None
                )
                if email_error:
                    row_errors.append({
                        "row_number": email_error.row_number,
                        "column_name": email_error.field,
                        "error_message": email_error.message,
                        "error_type": email_error.error_code.value,
                    })
                    breakdown["invalid_email"] = breakdown.get("invalid_email", 0) + 1

            # Customer name validation
            if row.get("customer_name"):
                name_error = NameValidator.validate(str(row["customer_name"]), row_idx + 1)
                if name_error:
                    row_errors.append({
                        "row_number": name_error.row_number,
                        "column_name": name_error.field,
                        "error_message": name_error.message,
                        "error_type": name_error.error_code.value,
                    })
                    breakdown["invalid_name"] = breakdown.get("invalid_name", 0) + 1

            # Country validation
            if row.get("country"):
                country_error = CountryValidator.validate(str(row["country"]), row_idx + 1)
                if country_error:
                    row_errors.append({
                        "row_number": country_error.row_number,
                        "column_name": country_error.field,
                        "error_message": country_error.message,
                        "error_type": country_error.error_code.value,
                    })
                    breakdown["invalid_country"] = breakdown.get("invalid_country", 0) + 1

            # Currency validation
            if row.get("currency"):
                currency_error = CurrencyValidator.validate(
                    str(row["currency"]),
                    row_idx + 1,
                    row_rule.valid_currencies if row_rule else None
                )
                if currency_error:
                    row_errors.append({
                        "row_number": currency_error.row_number,
                        "column_name": currency_error.field,
                        "error_message": currency_error.message,
                        "error_type": currency_error.error_code.value,
                    })
                    breakdown["invalid_currency"] = breakdown.get("invalid_currency", 0) + 1

            # Time validation
            if row.get("time"):
                time_error = TimeValidator.validate(str(row["time"]), row_idx + 1)
                if time_error:
                    row_errors.append({
                        "row_number": time_error.row_number,
                        "column_name": time_error.field,
                        "error_message": time_error.message,
                        "error_type": time_error.error_code.value,
                    })
                    breakdown["invalid_time"] = breakdown.get("invalid_time", 0) + 1

            # Phone — DB regex only, no hardcoded digit-length tables
            if row.get("phone_number"):
                phone_val = str(row["phone_number"]).strip()
                # Log first 10 phone numbers for debugging
                if row_idx < 10:
                    logger.info(f"Job {job_id}: Row {row_idx + 1} phone value: '{phone_val}' against regex: {phone_regex}")
                if not _is_valid_phone(phone_val, phone_regex):
                    row_errors.append({
                        "row_number": row_idx + 1,
                        "column_name": "phone_number",
                        "error_message": (
                            f"Phone '{phone_val}' does not match configured "
                            f"regex for country '{display_country}'"
                        ),
                        "error_type": "invalid_phone",
                    })
                    breakdown["invalid_phone"] += 1

            # Date
            if row.get("transaction_date"):
                date_val = str(row["transaction_date"]).strip()
                if not _is_valid_date(date_val):
                    row_errors.append({
                        "row_number": row_idx + 1,
                        "column_name": "transaction_date",
                        "error_message": f"Date '{date_val}' is not a recognised format",
                        "error_type": "invalid_date",
                    })
                    breakdown["invalid_date"] += 1
                else:
                    # Check for future dates if not allowed
                    if row_rule and not row_rule.allow_future_dates:
                        try:
                            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%d.%m.%Y"):
                                try:
                                    parsed_date = datetime.strptime(date_val, fmt)
                                    if parsed_date > datetime.now():
                                        row_errors.append({
                                            "row_number": row_idx + 1,
                                            "column_name": "transaction_date",
                                            "error_message": f"Date '{date_val}' is in the future",
                                            "error_type": "future_date",
                                        })
                                        breakdown["future_date"] = breakdown.get("future_date", 0) + 1
                                    break
                                except ValueError:
                                    continue
                        except Exception:
                            pass

            # Quantity - use new validator with country-specific limits
            if row.get("quantity") is not None:
                qty_error = QuantityValidator.validate(
                    row["quantity"],
                    row_idx + 1,
                    min_qty=row_rule.min_quantity if row_rule else 1,
                    max_qty=row_rule.max_quantity if row_rule else None
                )
                if qty_error:
                    row_errors.append({
                        "row_number": qty_error.row_number,
                        "column_name": qty_error.field,
                        "error_message": qty_error.message,
                        "error_type": qty_error.error_code.value,
                    })
                    breakdown["invalid_quantity"] = breakdown.get("invalid_quantity", 0) + 1
                    breakdown["negative_quantity"] += 1

            # Amount - use new validator with country-specific limits
            if row.get("amount") is not None:
                amount_error = AmountValidator.validate(
                    row["amount"],
                    row_idx + 1,
                    min_amount=row_rule.min_amount if row_rule else 0.01,
                    max_amount=row_rule.max_amount if row_rule else None
                )
                if amount_error:
                    row_errors.append({
                        "row_number": amount_error.row_number,
                        "column_name": amount_error.field,
                        "error_message": amount_error.message,
                        "error_type": amount_error.error_code.value,
                    })
                    breakdown["invalid_amount"] = breakdown.get("invalid_amount", 0) + 1
                    breakdown["negative_amount"] += 1

            # Payment mode — DB-loaded per country; None = accept all
            if row.get("payment_mode") and valid_modes is not None:
                pm = str(row["payment_mode"]).strip().upper()
                if pm not in valid_modes:
                    row_errors.append({
                        "row_number": row_idx + 1, "column_name": "payment_mode",
                        "error_message": (
                            f"Payment mode '{pm}' not in configured modes for "
                            f"'{display_country}': {valid_modes}"
                        ),
                        "error_type": "invalid_payment_mode",
                    })
                    breakdown["invalid_payment_mode"] += 1

            if row_errors:
                valid_mask[row_idx] = False
                error_logs.extend(row_errors)
                country_stats[display_country]["invalid"] += 1
                # Log first 10 errors for debugging
                if len(error_logs) <= 10:
                    for err in row_errors:
                        logger.info(f"Job {job_id}: Row {row_idx + 1} error - {err['error_type']}: {err['error_message']}")
            else:
                country_stats[display_country]["valid"] += 1

        # Enhanced duplicate detection (order_id, transaction_id, customer_id)
        duplicate_fields = ["order_id", "transaction_id", "customer_id"]
        for dup_field in duplicate_fields:
            if dup_field in df.columns:
                field_values = df[dup_field].to_list()
                seen: dict[str, int] = {}
                for i, val in enumerate(field_values):
                    if val and str(val).strip():
                        key = str(val).strip()
                        if key in seen:
                            error_logs.append({
                                "row_number": i + 1,
                                "column_name": dup_field,
                                "error_message": f"Duplicate {dup_field} '{key}' (first at row {seen[key]})",
                                "error_type": "duplicate_record",
                            })
                            if valid_mask[i]:
                                valid_mask[i] = False
                                breakdown["duplicate_record"] = breakdown.get("duplicate_record", 0) + 1
                                row = df.row(i, named=True)
                                raw_c = str(row.get("country") or "").strip().upper()
                                r = country_rules_map.get(raw_c) or fallback_rule
                                dc = r.country_code.upper() if r else display_country
                                if dc in country_stats and country_stats[dc]["valid"] > 0:
                                    country_stats[dc]["valid"] -= 1
                                    country_stats[dc]["invalid"] += 1
                        else:
                            seen[key] = i + 1

        # ── 5. Split valid / invalid ──────────────────────────────────────
        valid_indices   = [i for i, v in enumerate(valid_mask) if v]
        invalid_indices = [i for i, v in enumerate(valid_mask) if not v]
        valid_df   = df[valid_indices]   if valid_indices   else df.clear()
        invalid_df = df[invalid_indices] if invalid_indices else df.clear()
        valid_count   = len(valid_df)
        invalid_count = len(invalid_df)

        logger.info(f"Job {job_id}: Validation complete - {valid_count} valid, {invalid_count} invalid / {total_records}")
        logger.info(f"Job {job_id}: Validation breakdown: {breakdown}")
        
        # Log sample error messages for debugging
        if error_logs:
            logger.info(f"Job {job_id}: Sample error logs (first 10):")
            for err in error_logs[:10]:
                logger.info(f"  Row {err['row_number']}: {err['column_name']} - {err['error_message']} ({err['error_type']})")

        # ── 6. Write output files ─────────────────────────────────────────
        clean_path = storage_service.get_clean_output_path(job_id)
        error_path = storage_service.get_error_report_path(job_id)

        logger.info(f"Job {job_id}: Writing clean file to {clean_path}")
        # Cast phone_number to string and add leading apostrophe to prevent scientific notation in Excel
        clean_df = valid_df
        if "phone_number" in clean_df.columns:
            clean_df = clean_df.with_columns(
                (pl.lit("'") + pl.col("phone_number").cast(pl.Utf8)).alias("phone_number")
            )
        if "customer_phone" in clean_df.columns:
            clean_df = clean_df.with_columns(
                (pl.lit("'") + pl.col("customer_phone").cast(pl.Utf8)).alias("customer_phone")
            )
        clean_df.write_csv(str(clean_path))
        logger.info(f"Job {job_id}: Clean file written successfully")

        logger.info(f"Job {job_id}: Writing error file to {error_path}")
        if invalid_indices:
            row_error_map: dict[int, str] = {}
            for err in error_logs:
                ri = err["row_number"] - 1
                msg = f"{err['column_name']}: {err['error_message']}"
                row_error_map[ri] = (row_error_map.get(ri, "") + "; " + msg).lstrip("; ")
            reasons = [row_error_map.get(i, "Unknown error") for i in invalid_indices]
            # Cast phone_number to string and add leading apostrophe to prevent scientific notation in Excel
            error_df = invalid_df.with_columns(pl.Series("validation_errors", reasons))
            if "phone_number" in error_df.columns:
                error_df = error_df.with_columns(
                    (pl.lit("'") + pl.col("phone_number").cast(pl.Utf8)).alias("phone_number")
                )
            if "customer_phone" in error_df.columns:
                error_df = error_df.with_columns(
                    (pl.lit("'") + pl.col("customer_phone").cast(pl.Utf8)).alias("customer_phone")
                )
            error_df.write_csv(str(error_path))
        else:
            # Cast phone_number to string and add leading apostrophe to prevent scientific notation in Excel
            error_df = invalid_df
            if "phone_number" in error_df.columns:
                error_df = error_df.with_columns(
                    (pl.lit("'") + pl.col("phone_number").cast(pl.Utf8)).alias("phone_number")
                )
            if "customer_phone" in error_df.columns:
                error_df = error_df.with_columns(
                    (pl.lit("'") + pl.col("customer_phone").cast(pl.Utf8)).alias("customer_phone")
                )
            error_df.write_csv(str(error_path))
        logger.info(f"Job {job_id}: Error file written successfully")

        # Validation breakdown JSON
        breakdown["country_stats"] = country_stats
        try:
            import json
            bp = storage_service.get_validation_breakdown_path(job_id)
            with open(bp, "w") as fh:
                json.dump(breakdown, fh, indent=2)
        except Exception as e:
            logger.error(f"Job {job_id}: Failed to write breakdown: {e}")

        # Chunks — use Polars lazy slicing with configurable chunk size
        chunk_paths: list[str] = []
        chunk_record_counts: list[int] = []
        
        # Get chunk size from environment or default to 1000
        chunk_size = int(os.getenv("CHUNK_SIZE", str(CHUNK_SIZE)))
        logger.info(f"Job {job_id}: Using chunk size: {chunk_size}")
        
        if valid_count > 0:
            logger.info(f"Job {job_id}: Generating {len(range(0, valid_count, chunk_size))} chunks")
            for idx, start in enumerate(range(0, valid_count, chunk_size)):
                chunk_df = valid_df.slice(start, chunk_size)
                chunk_path = storage_service.get_chunk_output_path(job_id, idx + 1)
                chunk_df.write_csv(str(chunk_path))
                chunk_paths.append(str(chunk_path))
                chunk_record_counts.append(len(chunk_df))
            logger.info(f"Job {job_id}: Generated {len(chunk_paths)} chunks")
        else:
            logger.info(f"Job {job_id}: No valid records, skipping chunk generation")

        # Save validation logs to DB (capped at 500)
        try:
            from app.config.db import session_scope as _ss
            from app.models.logs import ValidationLogs
            from app.repositories.jobs import JobsRepository
            async with _ss() as session:
                repo = JobsRepository(session)
                logs = [
                    ValidationLogs(
                        job_id=job_id,
                        row_number=e["row_number"],
                        column_name=e.get("column_name"),
                        error_message=e["error_message"],
                        error_type=e["error_type"],
                    )
                    for e in error_logs[:500]
                ]
                if logs:
                    await repo.bulk_log_validation_errors(logs)
                    logger.info(f"Job {job_id}: Saved {len(logs)} validation logs to DB")
        except Exception as e:
            logger.error(f"Failed to save validation logs: {e}")

        # Verify output files exist before returning
        clean_file_exists = clean_path.exists()
        error_file_exists = error_path.exists()
        logger.info(
            f"Job {job_id}: Output file verification - "
            f"clean_file_exists={clean_file_exists}, error_file_exists={error_file_exists}"
        )
        
        if not clean_file_exists:
            logger.error(f"Job {job_id}: Clean file does not exist at {clean_path}")
        if not error_file_exists:
            logger.error(f"Job {job_id}: Error file does not exist at {error_path}")
        
        # Generate validation report and error summary
        validation_result = {
            "job_id": job_id,
            "status": "completed",
            "total_records": total_records,
            "valid_records": valid_count,
            "invalid_records": invalid_count,
            "clean_file_path": str(clean_path) if clean_file_exists else None,
            "error_report_path": str(error_path) if error_file_exists else None,
            "chunk_paths": chunk_paths,
            "chunk_record_counts": chunk_record_counts,
            "error_logs": error_logs[:100],
            "validation_breakdown": breakdown,
            "country_stats": country_stats,
        }
        
        try:
            validation_report_path = report_generator.generate_validation_report(job_id, validation_result)
            logger.info(f"Job {job_id}: Generated validation report at {validation_report_path}")
        except Exception as e:
            logger.error(f"Job {job_id}: Failed to generate validation report: {e}")
        
        try:
            error_summary_path = report_generator.generate_error_summary(job_id, error_logs)
            logger.info(f"Job {job_id}: Generated error summary at {error_summary_path}")
        except Exception as e:
            logger.error(f"Job {job_id}: Failed to generate error summary: {e}")
        
        # Generate AI insights
        try:
            ai_insights = await ai_insights_generator.generate_insights(job_id, validation_result)
            logger.info(f"Job {job_id}: Generated AI insights")
        except Exception as e:
            logger.error(f"Job {job_id}: Failed to generate AI insights: {e}")
            ai_insights = {"error": str(e)}
        
        # Calculate processing time and throughput
        processing_time = time.time() - start_time
        throughput = total_records / processing_time if processing_time > 0 else 0
        
        # Generate processing statistics
        processing_stats = {
            "job_id": job_id,
            "processing_time_seconds": round(processing_time, 2),
            "throughput_records_per_second": round(throughput, 2),
            "total_records": total_records,
            "valid_records": valid_count,
            "invalid_records": invalid_count,
            "validation_rate": round((valid_count / total_records) * 100, 2) if total_records > 0 else 0,
            "error_rate": round((invalid_count / total_records) * 100, 2) if total_records > 0 else 0,
        }
        
        try:
            stats_path = storage_service.get_processing_stats_path(job_id)
            with open(stats_path, "w") as f:
                json.dump(processing_stats, f, indent=2)
            logger.info(f"Job {job_id}: Generated processing stats at {stats_path}")
        except Exception as e:
            logger.error(f"Job {job_id}: Failed to generate processing stats: {e}")
        
        # Add processing metrics to validation result
        validation_result["processing_time_seconds"] = round(processing_time, 2)
        validation_result["throughput_records_per_second"] = round(throughput, 2)
        validation_result["ai_insights"] = ai_insights
        
        return validation_result


validation_service = ValidationService()
