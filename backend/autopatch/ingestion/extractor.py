"""Safe project ingestion and extraction module for AutoPatch.

Handles:
- Single file upload
- Folder upload
- ZIP extraction with Zip-Slip protection, decompression bomb prevention, and file-count caps
- GitHub repository shallow cloning
- Exclusion of extraneous directories (node_modules, venv, .git, build, dist)
"""

import os
import re
import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import Optional, Set
from autopatch.core.exceptions import AutoPatchError, SandboxSecurityError
from autopatch.core.logging import get_logger

logger = get_logger(__name__)

# Standard directory and file ignore set
DEFAULT_IGNORE_DIRS: Set[str] = {
    "node_modules",
    "venv",
    ".venv",
    "env",
    ".env",
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".tox",
    "dist",
    "build",
    "target",
    ".next",
    ".nuxt",
    ".cache",
    "coverage",
    ".egg-info",
}

DEFAULT_IGNORE_FILES: Set[str] = {
    ".DS_Store",
    "Thumbs.db",
}

# Limits for untrusted project uploads
MAX_EXTRACTED_SIZE_BYTES = 100 * 1024 * 1024  # 100 MB
MAX_FILE_COUNT = 5000
CLONE_TIMEOUT_SECONDS = 30


class IngestionError(AutoPatchError):
    """Raised when project ingestion or extraction fails."""
    pass


class SafeExtractor:
    """Safely extracts and prepares codebases for analysis."""

    def __init__(
        self,
        max_size_bytes: int = MAX_EXTRACTED_SIZE_BYTES,
        max_file_count: int = MAX_FILE_COUNT,
        ignore_dirs: Optional[Set[str]] = None,
        ignore_files: Optional[Set[str]] = None,
    ):
        self.max_size_bytes = max_size_bytes
        self.max_file_count = max_file_count
        self.ignore_dirs = ignore_dirs if ignore_dirs is not None else DEFAULT_IGNORE_DIRS
        self.ignore_files = ignore_files if ignore_files is not None else DEFAULT_IGNORE_FILES

    def should_ignore_path(self, path: Path) -> bool:
        """Determines if a given path should be skipped based on ignore rules."""
        parts = set(path.parts)
        if any(ignored in parts for ignored in self.ignore_dirs):
            return True
        if path.name in self.ignore_files or path.name.endswith(".pyc"):
            return True
        return False

    def extract_zip(self, zip_path: Path, destination: Path) -> Path:
        """Safely extracts a ZIP archive into destination.

        Guarantees:
        - Rejects Zip-Slip path traversal attempts
        - Enforces total uncompressed size limit
        - Enforces max file count
        """
        destination = destination.resolve()
        destination.mkdir(parents=True, exist_ok=True)

        if not zip_path.is_file():
            raise IngestionError(f"ZIP archive not found: {zip_path}")

        total_size = 0
        file_count = 0

        with zipfile.ZipFile(zip_path, "r") as archive:
            # 1. Inspect archive metadata before extracting any content
            for member in archive.infolist():
                # Check for path traversal (Zip-Slip)
                extracted_path = (destination / member.filename).resolve()
                if not str(extracted_path).startswith(str(destination)):
                    raise SandboxSecurityError(
                        f"Zip-Slip exploit detected: '{member.filename}' attempts path traversal outside destination."
                    )

                # Skip directories for size/count checks
                if member.is_dir():
                    continue

                file_count += 1
                if file_count > self.max_file_count:
                    raise IngestionError(
                        f"Archive exceeds maximum allowed file count ({self.max_file_count})."
                    )

                total_size += member.file_size
                if total_size > self.max_size_bytes:
                    raise IngestionError(
                        f"Archive exceeds maximum allowed uncompressed size ({self.max_size_bytes} bytes)."
                    )

            # 2. Extract safe files, respecting ignore list
            for member in archive.infolist():
                target_path = (destination / member.filename).resolve()
                if self.should_ignore_path(target_path):
                    continue

                if member.is_dir():
                    target_path.mkdir(parents=True, exist_ok=True)
                else:
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(member) as source, open(target_path, "wb") as target:
                        shutil.copyfileobj(source, target)

        logger.info(
            "Safely extracted ZIP archive",
            extra={"data": {"files": file_count, "bytes": total_size, "dest": str(destination)}},
        )
        return destination

    def extract_zip_bytes(self, zip_bytes: bytes, destination: Path) -> Path:
        """Safely extracts raw ZIP bytes into destination."""
        temp_zip = destination / "_temp_upload.zip"
        destination.mkdir(parents=True, exist_ok=True)
        temp_zip.write_bytes(zip_bytes)
        try:
            return self.extract_zip(temp_zip, destination)
        finally:
            if temp_zip.exists():
                temp_zip.unlink()

    def ingest_folder(self, source_folder: Path, destination: Path) -> Path:
        """Copies a source folder into the destination workspace, applying ignore rules."""
        source_folder = source_folder.resolve()
        destination = destination.resolve()

        if not source_folder.is_dir():
            raise IngestionError(f"Source folder does not exist: {source_folder}")

        destination.mkdir(parents=True, exist_ok=True)
        file_count = 0
        total_size = 0

        for root, dirs, files in os.walk(source_folder):
            # Prune ignored directories in-place
            dirs[:] = [d for d in dirs if d not in self.ignore_dirs]

            rel_root = Path(root).relative_to(source_folder)
            target_root = destination / rel_root
            target_root.mkdir(parents=True, exist_ok=True)

            for f in files:
                if f in self.ignore_files or f.endswith(".pyc"):
                    continue

                src_file = Path(root) / f
                if src_file.is_symlink():
                    # Reject symlinks pointing outside the source tree
                    real_path = src_file.resolve()
                    if not str(real_path).startswith(str(source_folder)):
                        logger.warning("Skipping external symlink", extra={"data": {"link": str(src_file)}})
                        continue

                file_count += 1
                if file_count > self.max_file_count:
                    raise IngestionError(f"Project exceeds file limit ({self.max_file_count})")

                file_size = src_file.stat().st_size
                total_size += file_size
                if total_size > self.max_size_bytes:
                    raise IngestionError(f"Project exceeds size limit ({self.max_size_bytes} bytes)")

                dst_file = target_root / f
                shutil.copy2(src_file, dst_file)

        return destination

    def ingest_single_file(self, file_path: Path, destination: Path) -> Path:
        """Ingests a single source file into destination workspace."""
        file_path = file_path.resolve()
        destination = destination.resolve()

        if not file_path.is_file():
            raise IngestionError(f"Single file not found: {file_path}")

        destination.mkdir(parents=True, exist_ok=True)
        dst_file = destination / file_path.name
        shutil.copy2(file_path, dst_file)
        return destination

    def clone_github_repo(self, repo_url: str, destination: Path) -> Path:
        """Shallow clones a public repository using git --depth 1.

        Validates URL format to prevent command injection.
        """
        # Strict URL validation: HTTPS or GIT over SSH
        pattern = re.compile(r"^(https://github\.com/[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+(?:\.git)?)$")
        if not pattern.match(repo_url):
            raise IngestionError(f"Invalid or unsupported GitHub repository URL: {repo_url}")

        destination = destination.resolve()
        destination.mkdir(parents=True, exist_ok=True)

        cmd = ["git", "clone", "--depth", "1", repo_url, str(destination)]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=CLONE_TIMEOUT_SECONDS,
                check=False,
            )
            if result.returncode != 0:
                raise IngestionError(f"Git clone failed: {result.stderr.strip()}")
        except subprocess.TimeoutExpired:
            raise IngestionError(f"Git clone timed out after {CLONE_TIMEOUT_SECONDS}s")

        # Remove the .git directory to treat cloned project cleanly
        git_dir = destination / ".git"
        if git_dir.exists():
            shutil.rmtree(git_dir, ignore_errors=True)

        return destination
