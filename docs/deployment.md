# AutoPatch: Production Deployment & Operations Guide

This guide covers deploying AutoPatch in production environments using Docker Compose, configuring enterprise storage, running repository inspections, generating interactive remediation dossiers, and connecting the IDE extension.

---

## 1. Quickstart: 1-Command Production Deployment

AutoPatch includes production-ready Docker containers for the FastAPI backend and Next.js frontend:

```bash
# 1. Clone the repository
git clone -b MainPrompt https://github.com/TarunK57/AutoPatch.git
cd AutoPatch

# 2. Launch backend and frontend services
docker compose up --build -d
```

### Verification
Once launched, verify service health:
```bash
# Check running containers
docker compose ps

# Backend Healthcheck:
curl -f http://localhost:8000/api/v1/openapi.json

# Web Dashboard:
open http://localhost:3000
```

---

## 2. Architecture & Service Topology

```
                  ┌───────────────────────────────┐
                  │    Developer / User Client    │
                  └──────────────┬────────────────┘
                                 │
                 HTTP / HTTPS    │    VS Code / IDE Extension
                                 ▼
              ┌───────────────────────────────────────┐
              │          Nginx / Traefik SSL          │
              └───────────┬───────────────┬───────────┘
                          │               │
       Port 3000          │               │ Port 8000
  (Web Dashboard)         │               │ (REST / SSE API)
                          ▼               ▼
           ┌──────────────────────┐  ┌──────────────────────┐
           │ autopatch-frontend   │  │  autopatch-backend   │
           │ (Next.js 14 / Monaco)│  │ (FastAPI / Uvicorn)  │
           └──────────────────────┘  └──────────┬───────────┘
                                                │
                          ┌─────────────────────┴─────────────────────┐
                          │                                           │
                          ▼                                           ▼
             ┌─────────────────────────┐                 ┌─────────────────────────┐
             │   Ingestion / Sandbox   │                 │     Audit Store / DB    │
             │   (Safe ZIP & Git Clone)│                 │ (SQLite / PostgreSQL)   │
             └─────────────────────────┘                 └─────────────────────────┘
```

---

## 3. Configuration & Environment Variables

Create a `.env` file in the project root:

```env
# Server Configuration
AUTOPATCH_ENV=production
AUTOPATCH_HOST=0.0.0.0
AUTOPATCH_PORT=8000
PORT=3000

# Security & Authentication
API_BEARER_TOKEN=dev_token_user_developer
SECRET_KEY=change_me_to_a_secure_random_string_32_bytes

# Optional Third-Party LLM Providers (Defaults to deterministic template patcher)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=AIza...

# Concurrency & Token Caps
CONCURRENCY_LIMIT=4
JOB_TOKEN_BUDGET=150000
BUG_TOKEN_BUDGET=30000

# Privacy Mode (Set to true to disable all external network calls)
AUTOPATCH_PRIVACY_MODE=false
```

---

## 4. End-to-End Ingestion & Analysis Workflows

### Option A: Uploading a ZIP Archive
1. Open the dashboard at `http://localhost:3000`.
2. Drag and drop any `.zip` archive containing your Python or JavaScript/TypeScript project.
3. The server validates the archive against Zip-Slip path traversal exploits and decompression bombs.
4. Click **"Process Codebase & Generate Project Map"**, review detected languages and entry points, and click **"Start Autonomous Scan"**.

### Option B: Ingesting a Git Repository
1. Provide a public or authenticated Git URL (e.g. `https://github.com/org/repo.git`) or local path.
2. The engine executes a safe shallow clone (`--depth 1`) with strict argument sanitization.
3. The engine parses ASTs, computes Ochiai SBFL suspiciousness scores, synthesizes Bug Reproducing Tests (BRTs), and runs differential sandbox validation.

### Option C: Triggering Analysis via CLI / cURL
```bash
# 1. Register a project
PROJECT_ID=$(curl -s -X POST http://localhost:8000/api/v1/projects \
  -H "Authorization: Bearer dev_token_user_developer" \
  -F "name=MyProject" \
  -F "file=@project.zip" | jq -r '.project_id')

# 2. Start the scan
JOB_ID=$(curl -s -X POST http://localhost:8000/api/v1/projects/$PROJECT_ID/scan \
  -H "Authorization: Bearer dev_token_user_developer" \
  -H "Content-Type: application/json" \
  -d '{"concurrency_limit": 3}' | jq -r '.job_id')

# 3. Stream live SSE pipeline traces
curl -N http://localhost:8000/api/v1/jobs/$JOB_ID/stream \
  -H "Authorization: Bearer dev_token_user_developer"
```

---

## 5. Generating & Exporting Remediation Reports

AutoPatch generates production audit dossiers in multiple standard formats:

| Format | URL Endpoint | Description |
|---|---|---|
| **Interactive HTML** | `GET /api/v1/projects/{id}/report?format=html` | Self-contained, responsive single-page dossier with KPIs, diffs, and print-to-PDF styles |
| **SARIF 2.1.0** | `GET /api/v1/projects/{id}/export?format=sarif` | OASIS standard for GitHub Security tab and CI ingestion |
| **Executive Markdown** | `GET /api/v1/projects/{id}/export?format=markdown` | Formatted Markdown summary with causal chains and test proof |
| **Unified Diff** | `GET /api/v1/projects/{id}/export?format=diff` | Standard patch file ready for `git apply` |
| **Patched Archive** | `GET /api/v1/projects/{id}/export?format=zip` | Downloadable ZIP of the entire codebase with fixes applied |

---

## 6. Attaching the IDE Extension

The AutoPatch extension integrates directly with **VS Code**, **Cursor**, **Windsurf**, and **Eclipse Theia**:

1. Compile the extension:
   ```bash
   cd vscode-extension
   npm install
   npm run compile
   ```
2. In VS Code / Cursor:
   - Run `F5` in VS Code to launch an Extension Development Host, or package as `.vsix`:
     ```bash
     npx @vscode/vsce package
     code --install-extension autopatch-1.0.0.vsix
     ```
3. Open any codebase in your editor:
   - Press `Cmd+Shift+P` (or `Ctrl+Shift+P`) and choose **"AutoPatch: Scan Entire Workspace for Bugs"**.
   - Defect squiggles appear directly under buggy lines.
   - Press `Cmd+.` to view Quick Fixes: **"💡 AutoPatch: Apply verified patch"** or **"🔍 AutoPatch: View Root Cause & BRT Evidence"**.

---

## 7. Scaling to Enterprise Kubernetes Clusters

For high-volume multi-tenant enterprise clusters:
- Replace SQLite with managed **PostgreSQL (AWS RDS / Cloud SQL)** via `DATABASE_URL`.
- Run worker pipelines using distributed Celery workers with a shared **Redis** queue.
- Use rootless **gVisor (`runsc`)** or **Firecracker** containers for sandboxed test execution.
