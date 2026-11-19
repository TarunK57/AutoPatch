"""Upload scanning and security validation for uploaded project archives and source trees."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import List, Tuple
from pydantic import BaseModel, Field

from autopatch.ingestion.extractor import MAX_FILE_COUNT, MAX_EXTRACTED_SIZE_BYTES
from autopatch.security.redaction import SecretRedactor


class UploadScanResult(BaseModel):
    """Result of pre-ingestion security scan on uploaded archives and repositories."""

    is_safe: bool = True
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    files_scanned: int = 0
    total_bytes: int = 0
    unredacted_secrets_detected: int = 0


class UploadScanner:
    """Scans incoming project files and archives to protect against Zip-Slip, DoS, and secret leaks."""

    def __init__(self):
        self.redactor = SecretRedactor()

    def scan_archive_bytes(self, archive_bytes: bytes) -> UploadScanResult:
        """Inspects raw zip archive bytes before unpacking."""
        result = UploadScanResult(total_bytes=len(archive_bytes))

        if len(archive_bytes) > MAX_EXTRACTED_SIZE_BYTES:
            result.is_safe = False
            result.errors.append(
                f"Archive exceeds maximum allowed size ({len(archive_bytes)} > {MAX_EXTRACTED_SIZE_BYTES} bytes)."
            )
            return result

        try:
            with zipfile.ZipFile(io.BytesIO(archive_bytes), "r") as zf:
                infolist = zf.infolist()
                result.files_scanned = len(infolist)

                if len(infolist) > MAX_FILE_COUNT:
                    result.is_safe = False
                    result.errors.append(
                        f"Archive contains too many files ({len(infolist)} > {MAX_FILE_COUNT})."
                    )
                    return result

                for info in infolist:
                    name = info.filename
                    # Zip slip check
                    if ".." in name or name.startswith("/") or name.startswith("\\"):
                        result.is_safe = False
                        result.errors.append(f"Malicious Zip-Slip path traversal pattern detected: '{name}'")
                        return result

                    # Sample code contents for secrets
                    if not info.is_dir() and info.file_size < 1_000_000:
                        try:
                            content = zf.read(info).decode("utf-8", errors="ignore")
                            redacted, mask_map = self.redactor.redact(content)
                            if mask_map:
                                result.unredacted_secrets_detected += len(mask_map)
                                result.warnings.append(
                                    f"Detected {len(mask_map)} raw secrets in '{name}'; automated redaction applied."
                                )
                        except Exception:
                            pass

        except zipfile.BadZipFile:
            result.is_safe = False
            result.errors.append("Invalid or corrupted zip archive format.")

        return result
