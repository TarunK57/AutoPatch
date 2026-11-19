from __future__ import annotations

import tempfile
from pathlib import Path
from fastapi.testclient import TestClient

from autopatch.api.main import app
from autopatch.api.routes import PROJECTS_DB, JOBS_DB, event_store
from autopatch.orchestrator.events import AuditEvent, EventType
from autopatch.security.retention import DataRetentionManager, RetentionPolicy


def test_purge_removes_all_artifacts_and_records():
    """
    Acceptance criterion: Purge removes all artifacts (extracted files, temporary copies,
    audit events, jobs and project metadata).
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        proj_dir = Path(tmp_dir) / "test_project_alpha"
        proj_dir.mkdir(parents=True)
        (proj_dir / "app.py").write_text("print('hello')\n")
        (proj_dir / "secret.key").write_text("dummy_secret\n")

        project_id = "proj-purge-1"
        job_id = "job-purge-1"

        # Seed in-memory DBs
        projects_db = {
            project_id: {
                "project_id": project_id,
                "name": "Alpha Service",
                "owner_id": "user_dev",
                "project_dir": str(proj_dir),
            }
        }
        jobs_db = {
            job_id: {
                "job_id": job_id,
                "project_id": project_id,
                "owner_id": "user_dev",
                "status": "COMPLETED",
            }
        }

        # Seed audit events
        event_store.append(
            AuditEvent(
                job_id=job_id,
                bug_id=f"{job_id}:app.py:1",
                event_type=EventType.JOB_STARTED,
                actor="TEST",
                payload={"info": "started"},
            )
        )
        assert len(event_store.get_events(job_id=job_id)) >= 1

        # Execute Purge
        manager = DataRetentionManager()
        report = manager.purge_project(
            project_id=project_id,
            project_dir=proj_dir,
            event_store=event_store,
            projects_db=projects_db,
            jobs_db=jobs_db,
        )

        # 1. Assert on-disk directory and all files are completely removed!
        assert not proj_dir.exists(), "Project directory must not exist on disk after purge"
        assert not (proj_dir / "app.py").exists()

        # 2. Assert all SQLite events were wiped
        remaining_events = event_store.get_events(job_id=job_id)
        assert len(remaining_events) == 0, "All audit events must be purged from event store"

        # 3. Assert project and jobs removed from memory state
        assert project_id not in projects_db
        assert job_id not in jobs_db
        assert report.success is True


def test_purge_endpoint_via_fastapi():
    """Verify that DELETE /api/v1/projects/{project_id}/purge removes all artifacts via REST API."""
    client = TestClient(app)
    headers = {"Authorization": "Bearer dev_token_user_developer"}

    # 1. Create a project
    create_res = client.post(
        "/api/v1/projects",
        json={"name": "Project To Purge"},
        headers=headers,
    )
    assert create_res.status_code == 201
    proj_id = create_res.json()["project_id"]

    # Verify project exists in DB
    assert proj_id in PROJECTS_DB
    proj_dir = Path(PROJECTS_DB[proj_id]["project_dir"])
    assert proj_dir.exists()

    # 2. Call purge endpoint
    purge_res = client.delete(
        f"/api/v1/projects/{proj_id}/purge",
        headers=headers,
    )
    assert purge_res.status_code == 200
    report = purge_res.json()
    assert report["success"] is True
    assert report["target_id"] == proj_id

    # 3. Verify directory is deleted from disk and project is removed from DB
    assert not proj_dir.exists()
    assert proj_id not in PROJECTS_DB

    # 4. Subsequent access returns 404
    get_res = client.get(f"/api/v1/projects/{proj_id}/bugs", headers=headers)
    assert get_res.status_code == 404
