"""Unit tests for safe extraction, zip-slip defense, and ingestion limits."""

import zipfile
from pathlib import Path
import pytest
from autopatch.core.exceptions import SandboxSecurityError
from autopatch.ingestion.extractor import IngestionError, SafeExtractor


def test_safe_zip_extraction(tmp_path: Path):
    """Verify normal, safe ZIP extraction with directory structure."""
    zip_path = tmp_path / "safe.zip"
    dest_dir = tmp_path / "extracted"

    with zipfile.ZipFile(zip_path, "w") as z:
        z.writestr("app/main.py", "print('hello world')")
        z.writestr("app/utils.py", "def add(a, b): return a + b")

    extractor = SafeExtractor()
    extractor.extract_zip(zip_path, dest_dir)

    assert (dest_dir / "app/main.py").is_file()
    assert (dest_dir / "app/utils.py").is_file()
    assert (dest_dir / "app/main.py").read_text() == "print('hello world')"


def test_zip_slip_exploit_rejected(tmp_path: Path):
    """Acceptance criterion: A malicious ZIP with path traversal is rejected."""
    malicious_zip = tmp_path / "malicious.zip"
    dest_dir = tmp_path / "target"

    # Create a malicious archive attempting to write outside target destination
    with zipfile.ZipFile(malicious_zip, "w") as z:
        z.writestr("../../etc/passwd", "root:x:0:0:root:/root:/bin/bash")

    extractor = SafeExtractor()
    with pytest.raises(SandboxSecurityError) as exc_info:
        extractor.extract_zip(malicious_zip, dest_dir)

    assert "Zip-Slip exploit detected" in str(exc_info.value)
    # Ensure nothing was written outside
    assert not (tmp_path / "etc/passwd").exists()


def test_zip_file_count_limit(tmp_path: Path):
    """Verify that archives with excessive file count are rejected."""
    bomb_zip = tmp_path / "many_files.zip"
    dest_dir = tmp_path / "target"

    with zipfile.ZipFile(bomb_zip, "w") as z:
        for i in range(15):
            z.writestr(f"file_{i}.txt", f"content {i}")

    # Set threshold low for testing
    extractor = SafeExtractor(max_file_count=10)
    with pytest.raises(IngestionError) as exc_info:
        extractor.extract_zip(bomb_zip, dest_dir)

    assert "exceeds maximum allowed file count" in str(exc_info.value)


def test_zip_size_limit(tmp_path: Path):
    """Verify that archives exceeding size limit are rejected."""
    big_zip = tmp_path / "big.zip"
    dest_dir = tmp_path / "target"

    with zipfile.ZipFile(big_zip, "w") as z:
        z.writestr("large.txt", "A" * 5000)

    extractor = SafeExtractor(max_size_bytes=1000)
    with pytest.raises(IngestionError) as exc_info:
        extractor.extract_zip(big_zip, dest_dir)

    assert "exceeds maximum allowed uncompressed size" in str(exc_info.value)


def test_folder_ingestion_ignores_extraneous_dirs(tmp_path: Path):
    """Verify folder ingestion skips node_modules, venv, and .git."""
    src = tmp_path / "source_project"
    dst = tmp_path / "ingested"

    # Create project layout
    (src / "src").mkdir(parents=True)
    (src / "src/index.py").write_text("x = 1")
    (src / "node_modules/package").mkdir(parents=True)
    (src / "node_modules/package/index.js").write_text("dummy")
    (src / ".venv/bin").mkdir(parents=True)
    (src / ".venv/bin/python").write_text("dummy")

    extractor = SafeExtractor()
    extractor.ingest_folder(src, dst)

    assert (dst / "src/index.py").is_file()
    assert not (dst / "node_modules").exists()
    assert not (dst / ".venv").exists()
