"""Validation report generator."""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
from app.services.storage import storage_service


class ReportGenerator:
    """Generates validation reports and summaries."""
    
    @staticmethod
    def generate_validation_report(job_id: str, validation_result: Dict[str, Any]) -> str:
        """Generate comprehensive validation report."""
        report_path = storage_service.get_validation_report_path(job_id)
        
        report = {
            "report_metadata": {
                "job_id": job_id,
                "generated_at": datetime.now().isoformat(),
                "report_type": "validation_summary"
            },
            "validation_summary": {
                "total_records": validation_result.get("total_records", 0),
                "valid_records": validation_result.get("valid_records", 0),
                "invalid_records": validation_result.get("invalid_records", 0),
                "validation_rate": round(
                    (validation_result.get("valid_records", 0) / validation_result.get("total_records", 1)) * 100, 2
                ) if validation_result.get("total_records", 0) > 0 else 0,
                "error_rate": round(
                    (validation_result.get("invalid_records", 0) / validation_result.get("total_records", 1)) * 100, 2
                ) if validation_result.get("total_records", 0) > 0 else 0
            },
            "error_breakdown": validation_result.get("validation_breakdown", {}),
            "country_statistics": validation_result.get("country_stats", {}),
            "file_outputs": {
                "clean_file": validation_result.get("clean_file_path"),
                "error_file": validation_result.get("error_report_path"),
                "chunks": {
                    "count": len(validation_result.get("chunk_paths", [])),
                    "paths": validation_result.get("chunk_paths", []),
                    "record_counts": validation_result.get("chunk_record_counts", [])
                }
            }
        }
        
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)
        
        return str(report_path)
    
    @staticmethod
    def generate_error_summary(job_id: str, error_logs: list) -> str:
        """Generate error summary report."""
        summary_path = storage_service.get_error_summary_path(job_id)
        
        # Group errors by type
        error_by_type: Dict[str, list] = {}
        for error in error_logs:
            error_type = error.get("error_type", "unknown")
            if error_type not in error_by_type:
                error_by_type[error_type] = []
            error_by_type[error_type].append(error)
        
        # Generate summary
        summary = {
            "summary_metadata": {
                "job_id": job_id,
                "generated_at": datetime.now().isoformat(),
                "total_errors": len(error_logs)
            },
            "error_by_type": {
                error_type: {
                    "count": len(errors),
                    "percentage": round((len(errors) / len(error_logs)) * 100, 2) if error_logs else 0,
                    "sample_errors": errors[:5]  # First 5 errors of each type
                }
                for error_type, errors in error_by_type.items()
            },
            "top_errors": sorted(
                [{"type": k, "count": len(v)} for k, v in error_by_type.items()],
                key=lambda x: x["count"],
                reverse=True
            )[:10]
        }
        
        with open(summary_path, "w") as f:
            json.dump(summary, f, indent=2)
        
        return str(summary_path)


report_generator = ReportGenerator()
