# AutoPatch: Autonomous End-to-End Bug Detection, Localization, Repair, and Verification Engine

AutoPatch is an enterprise-grade autonomous software repair and vulnerability remediation system designed for production engineering teams. It ingests codebases, detects defects through static and dynamic analysis, isolates root causes with Spectrum-Based Fault Localization (SBFL), synthesizes reproducible tests (BRT), generates candidate patches with AST templates and multi-model LLMs, validates changes in an isolated sandbox, and ranks fixes monotonically using Equivalent Patch Ranking (EPR).

Integrated with the **LuminaAI** web interface and native VS Code/Cursor extensions, AutoPatch pairs autonomous engineering with zero-hallucination verification and human-in-the-loop control.

---

## Autonomous Remediation Workflow

```
[ Ingest Codebase ]
  ├── 1-Click Official GitHub Portal (OAuth / Account Handle)
  ├── Remote Git Repository Clone (HTTPS / SSH / Branch)
  └── Direct ZIP / Tarball Source Ingestion
              │
              ▼
[ 1. Multi-Strategy Defect Detection ]
  ├── Static Tree-Sitter AST & Taint Tracking
  ├── Dynamic Test Crawlers (Pytest, Jest)
  ├── OWASP API Security Auditor (BOLA, Broken Auth, Resource Exhaustion, CORS)
  └── Predictive Bug Radar (Mutable Defaults, Unchecked Nulls, High Cyclomatic Complexity)
              │
              ▼
[ 2. Spectrum-Based Fault Localization (SBFL) ]
  ├── Ochiai, Tarantula, and DStar Suspiciousness Scoring
  └── Call-Graph Distance Pruning & Reachable Blast Radius Calculation
              │
              ▼
[ 3. Bug Reproducing Test (BRT) Synthesis ]
  ├── Automated Minimal Reproducer Test Generation
  └── Multi-Run Flakiness Filtering & Non-Determinism Sanitization
              │
              ▼
[ 4. Multi-Strategy Patch Synthesis & Committee Deliberation ]
  ├── Zero-Cost Deterministic AST Templates (Off-by-One, Null Guards, Bounds)
  ├── Multi-LLM Ensemble Generation (Gemini 1.5 Pro, Claude 3.5 Sonnet)
  ├── Few-Shot Transfer Learning from Historical Repair Memory Store
  └── AI Model Committee Debate (Offensive Security, Architecture, Anti-Hallucination)
              │
              ▼
[ 5. Verification & Sandbox Execution ]
  ├── Phase 1: Candidate Patch flips BRT from FAIL to PASS
  ├── Phase 2: Full Regression Test Suite execution in isolated MicroVM
  └── Anti-Overfitting Guards (Test Bypass & Collateral Drift Blocker)
              │
              ▼
[ 6. Monotonic Scoring & Equivalent Patch Ranking (EPR) ]
  ├── Monotonic Confidence Guarantees (Verified fixes strictly dominate unverified)
  └── Priority Ranking = Severity Weight × Confidence Score × Blast Radius
              │
              ▼
[ 7. Human-in-the-Loop Triage, Review & Deployment ]
  ├── Interactive Monaco Side-by-Side Diff Viewer
  ├── Bug Origin Archaeology (Git Blame SHA, Author, Flaw Age, PR reference)
  ├── 1-Click Pull Request Creation with Invariant Evidence Tables
  ├── Direct Git Branch Push (with Branch Protection & Fork Detection)
  ├── Download Patched Project ZIP (Zero Remote Mutation Option)
  └── Automated Documentation Generation (Nygard ADR, Changelog, CISO Brief)
```

---

## 7 Advanced Enterprise Intelligence Features

### 1. Predictive Bug Detection
- **Engine**: [`backend/autopatch/detection/predictive.py`](backend/autopatch/detection/predictive.py)
- **Capability**: Proactive static AST inspection detecting latent defects before they manifest in runtime crashes.
- **Rules Audited**:
  - `CWE-665`: Mutable default parameter values (`def fn(items=[])`).
  - High Cyclomatic Complexity: Flags functions with complexity $\ge 10$ needing decomposition.
  - Unchecked Nullable Returns: Identifies dereferences of functions returning `Optional` (`re.search()`, `dict.get()`) without preceding null guards.
  - Unmanaged Resource Leaks: Flags `open()` calls without `with` context management.
  - Suppressed Exception Masking: Catches bare `except: pass` anti-patterns hiding failures.

### 2. Code Hotspot Detection
- **Engine**: [`backend/autopatch/intelligence/hotspots.py`](backend/autopatch/intelligence/hotspots.py)
- **Capability**: Integrates directly with Git porcelain logs to compute commit churn velocity, multi-author entropy, and LOC complexity into a weighted hotspot hazard score ($0-100$).
- **Value**: Highlights volatile code regions that cause disproportionate bug regressions and merge conflicts.

### 3. AI Model Committee (Separate Deliberation Mode)
- **Engine**: [`backend/autopatch/intelligence/committee.py`](backend/autopatch/intelligence/committee.py)
- **Capability**: Autonomous tri-persona deliberation panel preventing model hallucinations:
  - **Dr. Evelyn Vance** (*Principal Offensive Security Researcher*): Probes boundary conditions, taint vectors, and exploitability.
  - **Marcus Thorne** (*Distinguished Systems Architect*): Analyzes computational complexity, memory overhead, and blast radius.
  - **Elena Rostova** (*Lead Formal Verification Engineer*): Enforces determinism, semantic invariance, and anti-hallucination checks.
- **Workflow**: Conducts multi-round structured debate, stance refinement, and final consensus voting with explicit dissenting minority opinions.

### 4. Long-Term Learning from Repairs
- **Engine**: [`backend/autopatch/storage/repair_memory.py`](backend/autopatch/storage/repair_memory.py)
- **Capability**: Persistent SQLite-backed exemplar knowledge base (`repair_memory.db`) storing verified bug-to-patch transformations.
- **Transfer Learning**: Retrieves nearest historical repair patterns across CWE classifications and injects them as few-shot context into the patch synthesis prompt.
- **Automated Learning Hook**: Automatically records every approved patch from triage into the repair bank for institutional memory retention.

### 5. OWASP API Security Testing
- **Engine**: [`backend/autopatch/security/api_security.py`](backend/autopatch/security/api_security.py)
- **Capability**: Specialized AST visitor auditing REST APIs (FastAPI, Flask, Django) against the OWASP API Security Top 10:
  - `API1:2023` BOLA / IDOR: Missing tenant/user ownership assertions on entity lookups.
  - `API2:2023` Broken Authentication: Endpoints lacking authentication dependencies or headers.
  - `API4:2023` Unrestricted Resource Consumption: Paginated listings missing `limit`/`max_results` caps.
  - `API8:2023` CORS Misconfigurations: Overly permissive `allow_origins=["*"]` on sensitive endpoints.

### 6. Bug Origin Archaeology
- **Engine**: [`backend/autopatch/git/origin_tracker.py`](backend/autopatch/git/origin_tracker.py)
- **Capability**: Porcelained `git blame` archaeology that tracks any defect back to its introducing commit SHA, committer identity, commit timestamp, Pull Request identifier, and total flaw age in days.
- **Value**: Gives security and engineering managers instant historical context on when and why a bug was introduced.

### 7. Automated Documentation Generator
- **Engine**: [`backend/autopatch/intelligence/documentation.py`](backend/autopatch/intelligence/documentation.py)
- **Capability**: Auto-generates three industry-standard documentation artifacts for any repaired project:
  - **Nygard Architecture Decision Record (ADR)**: Formal context, decision rationale, and consequences.
  - **Keep a Changelog Security Notes**: SemVer-aligned markdown release notes with security fixes and CVE references.
  - **CISO Executive Remediation Brief**: High-level risk summary, mean time to remediate (MTTR), and regulatory compliance posture.

### 8. Codebase Digital Twin & 3D Blast Radius Visualizer (High Impact)
- **Engine**: [`backend/autopatch/intelligence/digital_twin.py`](backend/autopatch/intelligence/digital_twin.py) & [`lumina/digital-twin-visualizer.js`](lumina/digital-twin-visualizer.js)
- **Capability**: Builds an interactive 3D topological model of the repository's functions, dependencies, APIs, and tests.
- **Pre-Patch Impact Analysis**: Before applying any candidate patch, visualizes which downstream components could break.
- **The Wow Moment**: An interactive 3D dependency graph lights up the directly modified functions with a pulsing fire aura, tracing laser energy pulses through affected callers and public API endpoints, calculating downstream blast radius percentage, critical APIs at risk, and tests exercised.

---

## User Interfaces

### 1. LuminaAI Web Portal (`lumina/`)
The primary responsive web suite served at `http://localhost:3000`:

- **AI Studio (`studio.html`)**:
  - Connect via the **Official GitHub Portal** or upload ZIP/tarball bundles.
  - Toggle analysis guardrails (Predictive Detection, Model Committee Mode, Zero Regression checks).
  - Live SSE streaming terminal output displaying real-time agent telemetry.
- **Issues Queue (`queue.html`)**:
  - Centralized bug triage with priority filters (Critical, High, Medium, Low), CWE categories, and confidence scores.
  - Batch export options: Interactive HTML Dossier, SARIF 2.1.0, Unified Diff, or Executive Markdown.
- **Interactive Review & Triage (`review.html`)**:
  - Side-by-side Monaco diff editor highlighting candidate patches.
  - **3D Codebase Digital Twin & Pre-Patch Blast Radius panel**: Rotates in 3D, highlights directly modified symbols, and computes downstream risk.
  - Bug Origin Archaeology card with introducing commit SHA and flaw age.
  - AI Model Committee deliberation card with vote breakdown and expert rationales.
  - Similar Learned Historical Repairs card with few-shot transfer links.
  - Deployment actions: **Create GitHub PR**, **Push Direct Branch**, or **Download Patched ZIP**.
- **Enterprise Defense & Intelligence Hub (`solutions.html`)**:
  - Dedicated tabbed workspace for all 8 enterprise capabilities.
  - Interactive full-page **3D Codebase Digital Twin** with orbit controls, type filtering, and patch blast simulator.
  - Live committee deliberation trigger and 1-click clipboard copy for ADRs and CISO briefs.
- **Observability Dashboard (`dashboard.html`)**:
  - Direct database-backed metrics: MTTR, verification rate, vulnerability breakdowns by severity, and chronological audit log reconstruction. Zero simulated/fake data.

### 2. VS Code / Cursor / Windsurf Extension (`vscode-extension/`)
- Native in-editor squiggly diagnostics on detected flaws.
- `Cmd+.` Lightbulb Quick-Fix applying sandboxed, verified patches in 1 click.
- Native webview showing SBFL causal chains and BRT test proof.

---

## REST API Reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/projects` | Register git repository or upload project archive |
| `POST` | `/api/v1/github/portal-connect` | 1-Click Official GitHub Portal connection & repo discovery |
| `GET` | `/api/v1/projects/{project_id}/predictive-analysis` | Proactive AST complexity & hazard inspection |
| `GET` | `/api/v1/projects/{project_id}/hotspots` | Git churn velocity and author spread hotspot analysis |
| `GET` | `/api/v1/projects/{project_id}/digital-twin` | Codebase Digital Twin 3D topological model & metrics |
| `GET` | `/api/v1/projects/{project_id}/bugs/{bug_id}/digital-twin-impact` | Pre-patch blast radius & downstream impact simulation |
| `GET` | `/api/v1/committee/members` | List active AI Committee personas and credentials |
| `POST` | `/api/v1/projects/{project_id}/committee/review` | Convene tri-model committee debate & consensus voting |
| `GET` | `/api/v1/observability/repair-memory` | Inspect persistent SQLite learned repair store |
| `GET` | `/api/v1/projects/{project_id}/bugs/{bug_id}/similar-repairs` | Retrieve historical few-shot repair exemplars |
| `GET` | `/api/v1/projects/{project_id}/api-security/audit` | Run OWASP API Security Top 10 compliance audit |
| `GET` | `/api/v1/projects/{project_id}/bugs/{bug_id}/origin` | Git blame archaeology tracing flaw origin and author |
| `GET` | `/api/v1/projects/{project_id}/documentation/adr` | Generate Nygard Architectural Decision Record |
| `GET` | `/api/v1/projects/{project_id}/documentation/changelog` | Generate Keep a Changelog security notes |
| `GET` | `/api/v1/projects/{project_id}/documentation/executive-brief` | Generate CISO Executive Remediation Brief |
| `POST` | `/api/v1/projects/{project_id}/decisions` | Accept or reject patch with automatic repair learning |
| `POST` | `/api/v1/projects/{project_id}/git/push-branch` | Push fix to remote Git branch with protection fallback |
| `POST` | `/api/v1/projects/{project_id}/git/pull-request` | Open formal Pull Request with evidence table |
| `GET` | `/api/v1/projects/{project_id}/export?format=zip` | Download complete patched codebase as ZIP |
| `GET` | `/api/v1/observability/dashboard` | Real-time SQLite KPI telemetry and audit trail |

---

## Evaluation Benchmark

AutoPatch includes a comprehensive benchmark under `eval/`:
- **30 Seeded Real-World Vulnerabilities**: Spanning boundary errors, null pointer dereferences, off-by-one loops, concurrency race conditions, input validation, and code injection.
- **SWE-bench Lite Adapter**: Fully compatible with standard software engineering benchmarks.
- **Ablation Studies**: Measures efficacy across Full Pipeline, No BRT, No SBFL, Templates Only (zero LLM cost), and LLM Only.
- **AutoCodeRover Failure Taxonomy**: Classifies all outcomes (Wrong Location, BRT Failure, No Patch, Regression, Overfitted Patch, Clean Verified).

Run the benchmark evaluation:
```bash
python eval/run.py
```

---

## Quickstart Guide

### 1. Docker Deployment
```bash
docker compose up --build -d
```
- Lumina AI Web UI: `http://localhost:3000`
- FastAPI REST / SSE Backend: `http://localhost:8000`
- OpenAPI Swagger Documentation: `http://localhost:8000/docs`

### 2. Manual Local Setup

#### Backend Setup
```bash
# Set up Python virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run complete pytest test suite (159 passing tests)
PYTHONPATH=backend pytest tests/ -v

# Launch backend with auto-reload
PYTHONPATH=backend uvicorn autopatch.api.main:app --host 0.0.0.0 --port 8000 --reload
```

#### Frontend Setup (Lumina Web Portal)
```bash
# Serve Lumina static web application
python3 -m http.server 3000 --directory lumina
```
Open `http://localhost:3000` in any modern web browser.

---

## Verification & Testing

AutoPatch enforces 100% test suite reliability with zero mock/simulated test data:
```bash
PYTHONPATH=backend pytest tests/ -v
```
```
============================= 159 passed in 46.58s =============================
```
- **Detection & SBFL**: Tests Ochiai/Tarantula formulas, distance pruning, and taint tracking.
- **BRT & Patcher**: Verifies minimal test reproduction, template synthesis, and prompt quarantine.
- **Verifier & Sandbox**: Verifies microVM process limits, regression blocking, and output capping.
- **Enterprise Features**: 19 dedicated tests covering predictive AST analysis, code hotspots, committee deliberation, repair memory learning, OWASP API auditing, bug origin tracking, and documentation generation.

---

## License

Apache-2.0
