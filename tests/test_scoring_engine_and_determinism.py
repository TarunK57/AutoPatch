"""Unit tests verifying deterministic bug ranking, 'why this rank' UI explanations, and config externalization."""

import json
import tempfile
from pathlib import Path
from uuid import uuid4

import pytest

from autopatch.scoring.config import ScoringConfig
from autopatch.scoring.engine import ScoringEngine
from autopatch.scoring.models import BugCategory


def test_ranking_is_strictly_deterministic():
    """Acceptance criterion: Ordering is 100% deterministic across repeated runs."""
    engine = ScoringEngine()

    # 5 test bug candidates with varied attributes
    candidates = [
        {
            "bug_id": "bug-style-1",
            "file_path": "src/style.py",
            "line_start": 10,
            "category": "style",
            "description": "Unused local variable",
            "detector_agreement": 0.50,
            "brt_status": "NONE",
            "verification_state": "NONE",
        },
        {
            "bug_id": "bug-sec-auth",
            "file_path": "src/auth/login.py",
            "line_start": 25,
            "category": "security",
            "cwe": "CWE-89",
            "description": "SQL Injection in auth handler",
            "detector_agreement": 0.95,
            "brt_status": "CONFIRMED",
            "verification_state": "VERIFIED",
            "epr": 100.0,
        },
        {
            "bug_id": "bug-crash-calc",
            "file_path": "src/math/calc.py",
            "line_start": 40,
            "category": "crash",
            "description": "Zero division in average computation",
            "detector_agreement": 0.85,
            "brt_status": "CONFIRMED",
            "verification_state": "VERIFIED",
            "epr": 100.0,
        },
        {
            "bug_id": "bug-logic-offbyone",
            "file_path": "src/utils/parser.py",
            "line_start": 15,
            "category": "wrong_output",
            "description": "Off-by-one in loop over lengths",
            "detector_agreement": 0.75,
            "brt_status": "CONFIRMED",
            "verification_state": "PLAUSIBLE_BUT_UNVERIFIED",
            "epr": 50.0,
        },
        {
            "bug_id": "bug-data-leak",
            "file_path": "src/db/leak.py",
            "line_start": 50,
            "category": "data_loss",
            "description": "Unclosed cursor leaking database connections",
            "detector_agreement": 0.80,
            "brt_status": "CONFIRMED",
            "verification_state": "VERIFIED",
            "epr": 100.0,
        },
    ]

    # Run ranking 5 separate times
    rankings = [
        [b.bug_id for b in engine.rank_findings(candidates, entry_points=["src/auth/login.py"])]
        for _ in range(5)
    ]

    # Every execution MUST yield identical order
    for r in rankings[1:]:
        assert r == rankings[0], f"Non-deterministic ordering detected: {r} != {rankings[0]}"

    # Verify top rank is the critical verified security flaw
    assert rankings[0][0] == "bug-sec-auth"
    # Verify lowest rank is the style lint flaw
    assert rankings[0][-1] == "bug-style-1"


def test_ui_shows_why_this_rank():
    """Acceptance criterion: The UI can show 'why this rank' with full transparency."""
    engine = ScoringEngine()

    candidate = {
        "bug_id": "bug-test-1",
        "file_path": "src/auth/service.py",
        "line_start": 12,
        "category": "security",
        "cwe": "CWE-79",
        "description": "XSS flaw in user greeting rendering",
        "detector_agreement": 0.90,
        "brt_status": "CONFIRMED",
        "verification_state": "VERIFIED",
        "epr": 100.0,
    }

    ranked = engine.rank_findings([candidate], entry_points=["src/main.py"])
    assert len(ranked) == 1
    item = ranked[0]

    explanation = item.priority.rank_explanation
    # Must explain rank and show formula inputs
    assert "Rank #1 of 1 bugs" in explanation
    assert "Priority score:" in explanation
    assert "Severity:" in explanation
    assert "Confidence:" in explanation
    assert "Impact:" in explanation
    assert "Category=security" in explanation
    assert "BRT=CONFIRMED" in explanation
    assert "Verification=VERIFIED" in explanation


def test_weights_live_in_config_not_code():
    """Acceptance criterion: Weights live in config file and can be modified externally."""
    with tempfile.TemporaryDirectory() as td:
        cfg_path = Path(td) / "custom_scoring.json"
        custom_cfg_data = {
            "version": "2.0.0",
            "description": "Custom experiment config",
            "category_weights": {
                "security": 0.50,
                "data_loss": 0.50,
                "crash": 0.50,
                "wrong_output": 1.00,  # Elevated wrong_output above security!
                "style": 0.10,
            },
            "reachability_weights": {
                "entry_point_direct": 1.0,
                "entry_point_indirect": 0.8,
                "public_api": 0.7,
                "internal_reachable": 0.5,
                "unreachable": 0.2,
            },
            "blast_radius": {
                "critical_path_multiplier": 1.0,
                "caller_count_scale": 0.0,
                "max_caller_boost": 0.0,
                "critical_path_keywords": [],
            },
            "confidence_weights": {
                "detector_agreement": 0.25,
                "brt_reproduction": 0.35,
                "verification_state": 0.25,
                "epr": 0.15,
                "overfitting_penalty": 0.30,
            },
            "verification_state_scores": {
                "VERIFIED": 1.0,
                "PLAUSIBLE_BUT_UNVERIFIED": 0.65,
                "NEEDS_REVIEW": 0.40,
                "FAILED": 0.05,
            },
            "brt_status_scores": {
                "CONFIRMED": 1.0,
                "UNCONFIRMED": 0.25,
                "NONE": 0.10,
            },
            "priority": {
                "severity_weight": 0.45,
                "confidence_weight": 0.35,
                "impact_weight": 0.20,
                "scale_factor": 100.0,
            },
        }
        cfg_path.write_text(json.dumps(custom_cfg_data))

        custom_config = ScoringConfig.load_from_file(cfg_path)
        assert custom_config.category_weights.wrong_output == 1.00
        assert custom_config.category_weights.security == 0.50

        # Initialize engine with custom config
        custom_engine = ScoringEngine(config=custom_config)

        # Under custom config, wrong_output has 1.00 base weight while security has 0.50
        candidates = [
            {
                "bug_id": "sec-bug",
                "file_path": "a.py",
                "category": "security",
                "detector_agreement": 0.8,
            },
            {
                "bug_id": "wrong-output-bug",
                "file_path": "b.py",
                "category": "wrong_output",
                "detector_agreement": 0.8,
            },
        ]

        ranked = custom_engine.rank_findings(candidates)
        # wrong-output-bug should rank #1 under the custom weights!
        assert ranked[0].bug_id == "wrong-output-bug"
        assert ranked[1].bug_id == "sec-bug"
