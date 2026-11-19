# AutoPatch: Autonomous End-to-End Bug Detection, Localization, Repair, and Verification Engine

AutoPatch is an autonomous software repair and vulnerability remediation system designed for production engineering teams. It ingests codebases, detects defects through static and dynamic analysis, isolates root causes with Spectrum-Based Fault Localization (SBFL), synthesizes reproducible tests (BRT), generates candidate patches with AST templates and LLMs, validates changes in an isolated sandbox, and ranks fixes monotonically using Equivalent Patch Ranking (EPR).

---

## Architecture Overview

AutoPatch operates as a staged pipeline:

```
[ Ingest / Repository / ZIP ]
              │
              ▼
[ 1. Bug Detection & Extraction ]
  ├── Pattern Detectors (AST, Tree-Sitter)
  ├── Static Crawlers & Call Graph Analyzers (NetworkX)
  └── Dynamic Test Failure Crawlers (Pytest/Jest)
              │
              ▼
[ 2. Fault Localization (SBFL) ]
  ├── Ochiai, Tarantula, DStar Suspiciousness Formulas
  └── Call-Graph Distance Pruning & Reachability Analysis
              │
              ▼
[ 3. Bug Reproducing Test (BRT) Synthesis ]
  ├── Automated Minimal Reproducer Generation
  └── Flakiness Sanitization & Non-Determinism Detection
              │
              ▼
[ 4. Multi-Strategy Patch Synthesis ]
  ├── Deterministic AST Rewrite Templates (Off-by-One, Null Checks, Bounds)
  ├── LLM Prompt Generation with Hard XML Isolation & Context Slicing
  └── Test-Guided Iterative Refinement
              │
              ▼
[ 5. Verification & Sandbox Execution ]
  ├── Multi-Phase Execution (BRT Pass + Full Regression Suite)
  └── Isolated Execution (Process Limits / Docker with CPU/RAM Quotas)
              │
              ▼
[ 6. Equivalent Patch Ranking (EPR) & Scoring ]
  ├── Priority = Severity Weight × Confidence × Impact
  ├── Anti-Overfitting Heuristics (Ast Diff, Deletion Ratios)
  └── Monotonic Confidence Guarantees
              │
              ▼
[ 7. Review, Observability & Git Integration ]
  ├── Next.js 14 Developer Dashboard & Monaco Side-by-Side Diff
  ├── SSE Event-Driven Stream & Audit Log Reconstruction
  ├── SQLite Tracing, Token Budgets & Trace Replay Engine
  └── Pull Request Generation with Evidence Tables & Commit Reverts
```

---

## Key Subsystems

### 1. Ingestion & Detection
- AST parsing using `tree-sitter` for Python and JavaScript.
- Call graph extraction via `networkx` for reachable blast radius calculation.
- Static pattern rules for boundary checks, null dereferences, format string exploits, and regex denial of service.

### 2. Localization (SBFL)
- Spectrum-based fault localization scoring:
  - **Ochiai**: $\frac{\text{failed}(s)}{\sqrt{\text{total\_failed} \cdot (\text{failed}(s) + \text{passed}(s))}}$
  - **Tarantula**: Ratio of failing executions vs total passing executions.
  - **DStar**: $\frac{\text{failed}(s)^*}{\text{passed}(s) + (\text{total\_failed} - \text{failed}(s))}$
- Call graph distance pruning to penalize unreachable or peripheral methods.

### 3. BRT (Bug Reproducing Test) Engine
- Synthesizes isolated, deterministic test scripts that fail on the unpatched codebase and pass once resolved.
- Flakiness verification runs each reproducer multiple times to prune flaky tests before patch synthesis.

### 4. Patch Synthesis & Validation Sandbox
- **Deterministic Templates**: Instant zero-cost repairs for common off-by-one errors, null guards, and boundary checks.
- **LLM Synthesis**: Generates semantically aware patches using prompt-injected defenses and code diff parsers.
- **Multi-phase Validation**: First checks if the candidate patch turns the BRT from FAIL to PASS, then executes the full regression suite to guarantee zero regressions.

### 5. Scoring & Equivalent Patch Ranking (EPR)
- **Deterministic Monotonicity**: A verified patch will never receive a lower confidence score than an unverified patch.
- **Priority Calculation**: Configurable weights for `category`, `reachability`, and `blast_radius`.
- **Anti-Overfitting**: Penalizes fixes that only delete code or bypass tests.

### 6. Observability, Cost Control & Replay
- Structured tracing in SQLite (`backend/autopatch/observability/structured_tracer.py`).
- Exact prompt hashing and LLM caching (`canonical_cache.py`).
- Token budget enforcement with automatic fallback to deterministic templates when limits are hit.
- Deterministic trace replay tool for debugging bug pipeline executions.

### 7. Security Hardening
- Complete threat model documented under `docs/threat-model.md` based on STRIDE.
- XML tag quarantine (`<untrusted_code>`) to neutralize prompt injection attacks.
- Secret redaction for credentials, API tokens, and private keys.
- Dependency vulnerability scanning and data retention purge API (`DELETE /api/v1/jobs/{id}/purge`).
- Privacy mode disabling all external network calls and third-party LLMs.

---

## Evaluation Benchmark

AutoPatch includes an evaluation harness under `eval/`:
- **30 Seeded Real-World Bugs**: Across Python and JavaScript spanning 7 categories (Boundary, Null Pointer, Off-by-One, Concurrency, Validation, Wrong Operator, Security).
- **SWE-bench Lite Adapter**: Compatible with standardized benchmark formats.
- **Ablation Studies**:
  - Full Pipeline
  - No BRT
  - No SBFL
  - Templates Only (zero LLM cost)
  - LLM Only
- **AutoCodeRover Failure Taxonomy**: Classifies all failure modes (Wrong Location, BRT Failure, No Patch, Regression, Overfitted Patch, Wrong Patch).
- **Bootstrap Confidence Intervals**: 95% CI computed over repeated runs.

To run the evaluation harness:
```bash
python eval/run.py
```
Output reports are generated at `eval/report.md` and `eval/results.json`.

---

## Quickstart Guide

### Prerequisites
- Python 3.9+
- Node.js 18+ & npm
- Docker (optional, for containerized sandbox isolation)

### 1. Backend Setup
```bash
# Clone the repository
git clone -b MainPrompt https://github.com/TarunK57/AutoPatch.git
cd AutoPatch

# Setup Python virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run pytest unit tests (139 passing tests)
pytest tests/
```

### 2. Frontend Setup
```bash
cd frontend
npm install
npm run build
npm run start
```
The web dashboard will be available at `http://localhost:3000`.

### 3. Running Backend Services
```bash
PYTHONPATH=backend python -m uvicorn autopatch.api.main:app --host 127.0.0.1 --port 8000
```
Swagger OpenAPI docs will be available at `http://127.0.0.1:8000/docs`.

---

## API Summary

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/projects` | Upload repository archive or register git URL |
| `POST` | `/api/v1/scans` | Trigger end-to-end scanning and repair pipeline |
| `GET` | `/api/v1/jobs/{job_id}/stream` | Server-Sent Events (SSE) live pipeline trace |
| `GET` | `/api/v1/bugs` | List detected bugs with priority ranking & filters |
| `GET` | `/api/v1/bugs/{bug_id}` | Detailed bug view (causal chain, diff, BRT evidence) |
| `POST` | `/api/v1/bugs/{bug_id}/decision` | Review action: `accept`, `reject`, `needs_review` |
| `POST` | `/api/v1/git/export` | Export patch files, unified diff, SARIF, or PR branch |
| `DELETE` | `/api/v1/jobs/{job_id}/purge` | Security purge of all cached job artifacts |

---

## Repository Structure

```
├── .github/workflows/autopatch-ci.yml  # GitHub Actions PR inline analysis
├── backend/
│   └── autopatch/
│       ├── api/                        # FastAPI REST routes and schemas
│       ├── core/                       # Data models, config, and audit log
│       ├── detection/                  # Static & dynamic bug extractors
│       ├── locator/                    # SBFL engine (Ochiai, Tarantula, DStar)
│       ├── reproducer/                 # BRT generation and flakiness verification
│       ├── patcher/                    # AST templates and LLM patch synthesis
│       ├── verifier/                   # Multi-phase sandbox test executor
│       ├── scoring/                    # Monotonic priority and EPR engine
│       ├── orchestrator/               # Concurrency queue and event pipeline
│       ├── observability/              # SQLite tracer, token budget & replay
│       ├── security/                   # Prompt quarantine, sanitizers, purge
│       └── git/                        # Branch manager, PR formatter, reverter
├── frontend/                           # Next.js 14, Tailwind, Monaco diff viewer
├── docs/                               # Threat model (STRIDE) documentation
├── eval/                               # Benchmark harness, 30 bugs, ablations
└── tests/                              # Comprehensive pytest suite (139 tests)
```

---

## License

Apache-2.0
