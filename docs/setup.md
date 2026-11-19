# AutoPatch: Comprehensive Project & Setup Documentation

Welcome to the definitive setup, architecture, and operational manual for **AutoPatch** — an autonomous, production-grade software bug detection, root-cause localization, patch synthesis, and verification engine.

---

## 1. System Architecture & Philosophy

AutoPatch automates the software engineering remediation lifecycle. Rather than acting as a simple linter or passive code reviewer, it runs a 5-stage staged verification pipeline:

```
[ Codebase Ingest (ZIP / Git Repo) ]
                 │
                 ▼
[ 1. Multi-Language Bug Extraction ]
  ├── Static AST Rules (Boundary, Null Pointer, Format Strings, Regex ReDoS)
  ├── Static Crawlers & Call Graph Analyzers (NetworkX)
  └── Dynamic Test Failure Crawlers (Pytest / Jest)
                 │
                 ▼
[ 2. Root Cause Localization (SBFL) ]
  ├── Spectrum-Based Fault Localization (Ochiai, Tarantula, DStar)
  └── Call-Graph Distance Pruning & Reachability Analysis
                 │
                 ▼
[ 3. Bug Reproducing Test (BRT) Synthesis ]
  ├── Automated Minimal Reproducer Test Generation
  └── Multi-Run Flakiness Sanitization & Non-Determinism Detection
                 │
                 ▼
[ 4. Multi-Strategy Patch Synthesis ]
  ├── Deterministic AST Rewrite Templates (Zero LLM Tokens, Instant)
  ├── Context-Sliced LLM Synthesis with XML Tag Defense (<untrusted_code>)
  └── Test-Guided Iterative Refinement Loops
                 │
                 ▼
[ 5. Differential Sandbox Verification ]
  ├── Phase 1: BRT Turn (FAIL -> PASS)
  ├── Phase 2: Full Regression Suite (0 Regressions Invariant)
  └── Anti-Overfitting Heuristics (Ast Change Ratio, Test Evasion Checks)
                 │
                 ▼
[ 6. Monotonic Scoring & Equivalent Patch Ranking (EPR) ]
  ├── Priority = Severity Weight × Confidence Calibration × Blast Radius Impact
  └── Monotonic Guarantee: Verified Bug Never Scores Lower Than Unverified
                 │
                 ▼
[ 7. Sentry-Style Workbench, IDE Extension & Git Delivery ]
  ├── Sentry-Inspired Obsidian Developer Dashboard & Monaco Diff Editor
  ├── Native VS Code / Cursor / Windsurf Extension (Gutter Diagnostics & Lightbulb 💡)
  └── Git Branch Generation, PR Evidence Tables, & Safe Commit Reverts
```

---

## 2. Repository Layout

```
AutoPatch/
├── backend/
│   └── autopatch/
│       ├── api/                        # FastAPI REST routes, SSE streams, auth, export
│       ├── ci/                         # GitHub Action runner for PR inline comments
│       ├── core/                       # Data models, exceptions, logging, audit store
│       ├── detection/                  # Multi-detector suite (AST rules, security, linters)
│       ├── git/                        # Git integration, PR branch builder, reverter
│       ├── ingestion/                  # SafeExtractor (Zip-Slip defense), ProjectMapper
│       ├── intelligence/               # Tree-sitter AST parsers (Python, JS/TS), CodeSearch
│       ├── locator/                    # SBFL engine (Ochiai, Tarantula, DStar)
│       ├── observability/              # SQLite tracer, canonical cache, token budgets, replay
│       ├── orchestrator/               # Async queue, concurrency manager, audit events
│       ├── patcher/                    # AST templates, LLM prompt repair, retry loop
│       ├── reproducer/                 # BRT synthesis, flakiness verifier, sandbox runner
│       ├── scoring/                    # Monotonic priority engine, severity & confidence
│       ├── security/                   # Prompt quarantine, secret redactor, purge API
│       └── verifier/                   # Differential sandbox, EPR ranking, anti-overfitting
├── frontend/                           # Sentry-inspired Next.js 14 web application
│   ├── src/
│   │   ├── app/                        # App router, globals.css (Sentry dark obsidian theme)
│   │   ├── components/
│   │   │   ├── actions/                # ReviewActionModal (Rule 1: Human Approval)
│   │   │   ├── bug/                    # BugReportScreen (6-section Sentry dossier)
│   │   │   ├── common/                 # KeyboardShortcutsModal (?)
│   │   │   ├── dashboard/              # DashboardScreen (Health score, MTTR, sparklines)
│   │   │   ├── diff/                   # MonacoDiffViewer (Side-by-side / inline diff)
│   │   │   ├── export/                 # ExportModal (HTML, SARIF, Markdown, Diff, PR)
│   │   │   ├── layout/                 # Sentry-style Header.tsx and Sidebar.tsx
│   │   │   ├── queue/                  # BugQueueScreen (Sentry Issues Stream)
│   │   │   ├── trace/                  # LiveTracePanel (SSE live agent streaming)
│   │   │   └── upload/                 # UploadScreen (ZIP drag-drop & Git clone)
│   │   ├── services/                   # ApiService (REST & SSE client)
│   │   └── types/                      # TypeScript domain models
│   ├── tailwind.config.ts              # Sentry brand tokens (sentry-purple, sentry-card)
│   └── package.json
├── vscode-extension/                   # Native IDE Extension (VS Code, Cursor, Windsurf)
│   ├── src/
│   │   ├── apiClient.ts                # AutoPatch backend client
│   │   ├── codeActionProvider.ts       # Quick Fix lightbulb (💡 "Apply verified patch")
│   │   ├── diagnosticsProvider.ts      # Gutter squigglies with severity & line numbers
│   │   ├── extension.ts                # Entrypoint, status bar, command dispatcher
│   │   ├── reportWebview.ts            # Native in-IDE webview panel
│   │   └── types.ts                    # Extension types
│   ├── dist/                           # Compiled JavaScript bundle
│   ├── package.json                    # Extension manifest and contributions
│   └── tsconfig.json
├── docs/
│   ├── deployment.md                   # Production deployment manual
│   ├── setup.md                        # Complete project setup documentation
│   └── threat-model.md                 # STRIDE security threat model
├── eval/                               # Evaluation benchmark harness
│   ├── ablations/                      # Ablation studies (No-BRT, No-SBFL, Templates-Only)
│   ├── dataset/                        # 30 seeded bugs in Python/JS across 7 categories
│   ├── metrics/                        # Failure taxonomy (AutoCodeRover) & bootstrap CIs
│   ├── reporter/                       # Markdown & JSON report generator
│   └── run.py                          # Single-command evaluation runner
├── tests/                              # Pytest test suite (143 unit & benchmark tests)
├── Dockerfile.backend                  # Production multi-stage Python container
├── Dockerfile.frontend                 # Production multi-stage Next.js container
├── docker-compose.yml                  # Production Docker Compose orchestration
├── requirements.txt                    # Python dependencies
└── pytest.ini                          # Pytest configuration
```

---

## 3. Prerequisites & Environment Setup

### System Requirements
- **OS**: macOS, Linux (Ubuntu 20.04+), or Windows with WSL2
- **Python**: `3.9` to `3.12` (Python 3.11 recommended)
- **Node.js**: `18.x` or `20.x` LTS
- **npm**: `9.x` or `10.x`
- **Git**: `2.30+` installed in `PATH`
- **Docker & Docker Compose**: Optional for local development; required for containerized production

---

## 4. Local Development Setup

### 4.1. Backend Setup
```bash
# 1. Navigate to project root
cd /path/to/AutoPatch

# 2. Create and activate a Python virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# 3. Install backend dependencies
pip install -r requirements.txt

# 4. Verify installation by running test suite (143 passing tests)
pytest tests/

# 5. Launch FastAPI backend server
PYTHONPATH=backend python -m uvicorn autopatch.api.main:app --host 127.0.0.1 --port 8000 --reload
```
- Interactive Swagger OpenAPI Docs: `http://127.0.0.1:8000/docs`
- ReDoc Docs: `http://127.0.0.1:8000/redoc`

### 4.2. Frontend Setup (Sentry-Inspired Workbench)
```bash
# 1. Navigate to frontend directory
cd frontend

# 2. Install Node dependencies
npm install

# 3. Build production bundle (or run development server)
npm run build
npm run start   # Or 'npm run dev' for development mode with hot-reloading
```
- Open your browser at: `http://localhost:3000`

---

## 5. One-Command Production Docker Deployment

To launch the complete platform in production:

```bash
docker compose up --build -d
```

### Checking Container Health
```bash
# Inspect container status
docker compose ps

# Inspect backend logs
docker compose logs -f backend

# Verify healthcheck endpoint
curl -f http://localhost:8000/api/v1/openapi.json
```

---

## 6. Sentry-Style User Interface Guide

The frontend is modeled directly on **Sentry's industry-standard developer observability interface**:

### 1. Issues Stream (`BugQueueScreen`)
- **Query Filter Bar**: Supports Sentry syntax like `is:unresolved`, `severity:critical`, `category:security`, `has:patch`.
- **Status Tabs**: Rapid switching between `Unresolved`, `Resolved with Patch`, and `All Issues`.
- **Stream Rows**:
  - Left vertical colored bar reflecting severity (Crimson for Critical, Orange for High, Amber for Medium, Cyan for Low).
  - Checkbox for batch triage operations.
  - Bug title and CWE identifier.
  - Monospace breadcrumb: `src/analytics/reporter.py in generate_metrics:42`.
  - Tags: `Python 3.11`, `Ochiai: 0.94`, `BRT: Passed`, `0 Regressions`.
  - **Visual Event Sparkline**: Sentry-style mini bar chart reflecting blast radius and defect recurrence.
  - Monotonic Priority score badge (`94 / 100`).

### 2. Issue Dossier & Remediation View (`BugReportScreen`)
- Top breadcrumbs bar (`Projects > Ecommerce-Core > Issues > #AP-104`).
- Header action buttons:
  - **Resolve with Patch (A)**: Sentry-style primary green resolution button.
  - **Reject (R)** & **Needs Review (N)**.
  - **Synthesize Alternative (EPR)**.
- 5-Tab Content Navigation:
  1. **Verified Patch & Code Diff**: Monaco Diff Editor (Side-by-side / inline) highlighting added and removed lines.
  2. **Root Cause & SBFL Heatmap**: Mathematical Ochiai score breakdown and call-graph path.
  3. **BRT Test Proof**: Console log showing test failure before patch, test pass after patch, and regression pass.
  4. **Causal Breadcrumbs**: Sentry-style step-by-step breadcrumb trail of events leading to the flaw.
  5. **Audit Trail**: Append-only tamper-proof event history.

### 3. Performance & Health Telemetry (`DashboardScreen`)
- Sentry-style **Codebase Health Score** meter with historical trend comparison (`+6% vs last scan`).
- 4 Primary Metric Cards with inline SVG sparklines:
  - Detected Issues volume
  - Zero-Regression Pass Rate (100%)
  - Autonomous MTTR (2.4s per defect)
  - Critical flaws requiring attention
- Severity distribution breakdown and highest priority unresolved flaw cards.

### 4. Live Agent Trace Panel (`LiveTracePanel`)
- Slide-out terminal streamed in real time via Server-Sent Events (SSE).
- Step-by-step logs for Detector, Locator, Reproducer, Patcher, and Verifier.
- Real-time token usage meter and USD cost tracker.
- Clean **Cancel Job** button.

---

## 7. Native IDE Extension Setup (VS Code / Cursor / Windsurf)

AutoPatch includes a native extension located under [`vscode-extension/`](file:///Users/niharchavan/Downloads/AntoPatch/vscode-extension):

### Installation & Packaging
```bash
cd vscode-extension

# 1. Install dependencies
npm install

# 2. Compile TypeScript
npm run compile

# 3. Package as .vsix installer
npx @vscode/vsce package

# 4. Install into VS Code or Cursor
code --install-extension autopatch-1.0.0.vsix
```

### In-Editor Features
- **In-Editor Squigglies**: Highlights defects with red (Critical/High) or yellow (Medium) squiggly underlines.
- **1-Click Quick Fix (Lightbulb 💡)**: Press `Cmd+.` / `Ctrl+.` on any flagged line:
  - `💡 AutoPatch: Apply verified patch (Confidence: X%)`
  - `🔍 AutoPatch: View Root Cause & BRT Evidence`
- **Native Webview Dossier**: Opens an in-editor panel showing diffs, causal chains, and BRT test proof.
- **Commands**:
  - `autopatch.scanWorkspace`: Scan Entire Workspace
  - `autopatch.scanActiveFile`: Scan Currently Focused File
  - `autopatch.openDashboard`: Open Sentry-style Web Workbench

---

## 8. Evaluation Benchmark Harness (`eval/`)

AutoPatch includes an evaluation harness under `eval/` benchmarked against 30 real-world bugs across 7 categories:

```bash
# Run the complete evaluation benchmark
python eval/run.py
```

### Output Reports
- Markdown Report: `eval/report.md`
- JSON Results: `eval/results.json`
- Metrics Computed:
  - Detection Precision & Recall
  - Localization Hit@1 and Hit@3
  - Candidate BRT rate & Plausible BRT rate
  - Patch Plausible Rate (passes oracle test)
  - Regression Rate (strictly 0.0%)
  - Equivalent Patch Ranking (EPR) Top-1 Precision
  - Bootstrap 95% Confidence Intervals

---

## 9. Security Hardening & Threat Model (STRIDE)

AutoPatch is hardened against untrusted codebase inputs:
- **STRIDE Threat Model**: Detailed in [`docs/threat-model.md`](file:///Users/niharchavan/Downloads/AntoPatch/docs/threat-model.md).
- **XML Tag Quarantine**: Ingested code and issue texts are wrapped in `<untrusted_code>` XML blocks so prompt injection instructions (e.g. "ignore previous instructions") are treated strictly as inert data.
- **Zip-Slip Protection**: Rejects archives attempting path traversal outside target workspaces.
- **Secret Redaction**: Automatically redacts API keys, passwords, and private tokens from traces and logs.
- **Privacy Mode**: Set `AUTOPATCH_PRIVACY_MODE=true` to disable all outbound network and third-party LLM calls, using local deterministic templates exclusively.
- **Data Retention & Purge**: `DELETE /api/v1/jobs/{job_id}/purge` immediately deletes all cached artifacts and files.

---

## 10. REST API Reference Summary

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/projects` | Register project via ZIP upload (`file`) or Git URL (`github_url`) |
| `GET` | `/api/v1/projects` | List projects owned by the authenticated user |
| `POST` | `/api/v1/projects/{id}/scan` | Trigger autonomous defect scan and repair pipeline |
| `GET` | `/api/v1/jobs/{id}` | Get scan progress, status, token metrics, and cost |
| `GET` | `/api/v1/jobs/{id}/stream` | SSE live stream of agent traces and events |
| `POST` | `/api/v1/jobs/{id}/cancel` | Cleanly cancel a running scan job |
| `POST` | `/api/v1/jobs/{id}/resume` | Resume an interrupted scan job from the last committed stage |
| `GET` | `/api/v1/projects/{id}/bugs` | List ranked bugs ordered deterministically by Priority score |
| `GET` | `/api/v1/bugs/{id}` | Detailed bug view (causal chain, diff, BRT evidence) |
| `POST` | `/api/v1/bugs/{id}/decision` | Record human review action: `APPROVED`, `REJECTED`, `NEEDS_REVIEW` |
| `GET` | `/api/v1/projects/{id}/report` | Standalone interactive HTML or downloadable report |
| `GET` | `/api/v1/projects/{id}/export` | Export artifacts in `html`, `sarif`, `markdown`, `diff`, or `zip` format |
| `POST` | `/api/v1/projects/{id}/git/branch` | Create a Git branch containing only accepted patches |
| `POST` | `/api/v1/projects/{id}/git/pull-request` | Open a GitHub Pull Request with Markdown evidence tables |
| `DELETE` | `/api/v1/jobs/{id}/purge` | Purge job data according to retention limits |

---

## 11. Troubleshooting & FAQ

#### Q: How do I resolve `Address already in use` for port 8000 or 3000?
Find the process occupying the port and terminate it:
```bash
lsof -i :8000 | awk 'NR>1 {print $2}' | xargs kill -9
lsof -i :3000 | awk 'NR>1 {print $2}' | xargs kill -9
```

#### Q: Can AutoPatch run completely offline without internet or LLM keys?
**Yes.** AutoPatch operates with **Zero External Dependencies** by using its deterministic AST rewrite engine (`DeterministicTemplatePatcher`). You can explicitly enable Privacy Mode by setting `AUTOPATCH_PRIVACY_MODE=true`.

#### Q: How does AutoPatch prevent patches from breaking existing code?
Every synthesized patch must pass two independent verification gates:
1. It must turn the minimal Bug Reproducing Test (BRT) from **FAIL** to **PASS**.
2. It must execute against the **entire existing test suite** with **strictly 0 regressions**. Any patch that fails either gate is immediately rejected.
