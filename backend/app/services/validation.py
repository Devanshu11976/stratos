import re
import logging
import traceback
import polars as pl
import pandera.polars as pa
from pathlib import Path
from app.services.storage import storage_service
from app.validators.rules import build_pandera_schema

logger = logging.getLogger("xeno.validation")

CHUNK_SIZE = 1000

EXPECTED_COLUMNS = [
    "order_id", "product_id", "quantity", "amount",
    "phone_number", "payment_mode", "transaction_date",
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
_FALLBACK_PHONE_REGEX = r"^\+?\d{7,15}$"


def _is_valid_phone(phone_val: str, phone_regex: str) -> bool:
    """Validate phone using the DB-supplied regex exclusively.
    No hardcoded digit-length tables — fully config-driven."""
    return bool(re.match(phone_regex, phone_val.strip()))


def _is_valid_date(date_val: str) -> bool:
    from datetime import datetime
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%d.%m.%Y"):
        try:
            datetime.strptime(date_val, fmt)
            return True
        except ValueError:
            continue
    return False


class ValidationService:
    async def process_dataset(self, job_id: str, file_path: str, country_code: str) -> dict:
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
                lf = pl.scan_csv(file_path, infer_schema_length=0)
                df = lf.collect()
            elif file_ext in (".xlsx", ".xls"):
                # fastexcel does not support lazy scan; read fully but streaming-friendly
                df = pl.read_excel(file_path, infer_schema_length=0)
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

            # Surface Pandera failures for this row
            for pe in pandera_errors.get(row_idx, []):
                row_errors.append({
                    "row_number": row_idx + 1,
                    "column_name": pe.split(":")[0] if ":" in pe else "schema",
                    "error_message": f"Schema check failed: {pe}",
                    "error_type": "pandera_schema",
                })
                breakdown["pandera_schema"] += 1

            # Missing fields
            for col in EXPECTED_COLUMNS:
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

            # Phone — DB regex only, no hardcoded digit-length tables
            if row.get("phone_number"):
                phone_val = str(row["phone_number"]).strip()
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

            # Quantity
            if row.get("quantity") is not None:
                try:
                    if float(str(row["quantity"])) < 0:
                        row_errors.append({
                            "row_number": row_idx + 1, "column_name": "quantity",
                            "error_message": f"Negative quantity: {row['quantity']}",
                            "error_type": "negative_quantity",
                        })
                        breakdown["negative_quantity"] += 1
                except (ValueError, TypeError):
                    row_errors.append({
                        "row_number": row_idx + 1, "column_name": "quantity",
                        "error_message": f"Non-numeric quantity: {row['quantity']}",
                        "error_type": "negative_quantity",
                    })
                    breakdown["negative_quantity"] += 1

            # Amount
            if row.get("amount") is not None:
                try:
                    if float(str(row["amount"])) < 0:
                        row_errors.append({
                            "row_number": row_idx + 1, "column_name": "amount",
                            "error_message": f"Negative amount: {row['amount']}",
                            "error_type": "negative_amount",
                        })
                        breakdown["negative_amount"] += 1
                except (ValueError, TypeError):
                    row_errors.append({
                        "row_number": row_idx + 1, "column_name": "amount",
                        "error_message": f"Non-numeric amount: {row['amount']}",
                        "error_type": "negative_amount",
                    })
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
            else:
                country_stats[display_country]["valid"] += 1

        # Duplicate order_ids (vectorised via Polars)
        if "order_id" in df.columns:
            order_ids = df["order_id"].to_list()
            seen: dict[str, int] = {}
            for i, oid in enumerate(order_ids):
                if oid and str(oid).strip():
                    key = str(oid).strip()
                    if key in seen:
                        error_logs.append({
                            "row_number": i + 1,
                            "column_name": "order_id",
                            "error_message": f"Duplicate order_id '{key}' (first at row {seen[key]})",
                            "error_type": "duplicate_order_id",
                        })
                        if valid_mask[i]:
                            valid_mask[i] = False
                            breakdown["duplicate_order_id"] += 1
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
        valid_df.write_csv(str(clean_path))
        logger.info(f"Job {job_id}: Clean file written successfully")

        logger.info(f"Job {job_id}: Writing error file to {error_path}")
        if invalid_indices:
            row_error_map: dict[int, str] = {}
            for err in error_logs:
                ri = err["row_number"] - 1
                msg = f"{err['column_name']}: {err['error_message']}"
                row_error_map[ri] = (row_error_map.get(ri, "") + "; " + msg).lstrip("; ")
            reasons = [row_error_map.get(i, "Unknown error") for i in invalid_indices]
            invalid_df.with_columns(pl.Series("validation_errors", reasons)).write_csv(str(error_path))
        else:
            invalid_df.write_csv(str(error_path))
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

        # Chunks — use Polars lazy slicing
        chunk_paths: list[str] = []
        chunk_record_counts: list[int] = []
        if valid_count > 0:
            logger.info(f"Job {job_id}: Generating {len(range(0, valid_count, CHUNK_SIZE))} chunks")
            for idx, start in enumerate(range(0, valid_count, CHUNK_SIZE)):
                chunk_df = valid_df.slice(start, CHUNK_SIZE)
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
        
        return {
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


validation_service = ValidationService()
