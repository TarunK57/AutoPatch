"""Persistent storage subsystem for AutoPatch projects, jobs, findings, and decisions."""

from autopatch.storage.db import DatabaseManager, get_storage

__all__ = ["DatabaseManager", "get_storage"]
