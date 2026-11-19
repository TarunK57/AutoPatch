# AutoPatch IDE Extension for VS Code / Cursor / Windsurf

Autonomous software defect detection, root-cause localization (SBFL), test-guided repair (BRT), and verified patching directly inside your development environment.

---

## Features

- **In-Editor Flaw Diagnostics**: Highlights vulnerabilities and bugs directly in your code with severity levels (Critical, High, Medium, Low), line ranges, and category tags.
- **Spectrum-Based Fault Localization (SBFL)**: Pinpoints exact buggy lines using Ochiai, Tarantula, and DStar suspiciousness formulas.
- **1-Click Quick Fix (Lightbulb 💡)**: Apply sandboxed, regression-verified patches instantly with a single keyboard shortcut (`Cmd+.` / `Ctrl+.`).
- **Interactive In-IDE Dossier**: Opens a native webview panel displaying root cause causal chains, before/after diffs, and Bug Reproducing Test (BRT) execution results.
- **Multi-Language Support**: Full AST intelligence and verification for **Python** and **JavaScript / TypeScript**.
- **Automated Webhook & Dashboard Sync**: View or download complete HTML/SARIF/Markdown reports directly from the IDE.

---

## Installation & Setup

### 1. Requirements
Ensure the AutoPatch backend engine is running:
```bash
# In the root repository directory
PYTHONPATH=backend python -m uvicorn autopatch.api.main:app --host 127.0.0.1 --port 8000
```

### 2. Compile Extension
```bash
cd vscode-extension
npm install
npm run compile
```

### 3. Package as .vsix (Optional)
To create a standalone `.vsix` installer for distribution:
```bash
npx @vscode/vsce package
```
Install in VS Code:
```bash
code --install-extension autopatch-1.0.0.vsix
```

---

## Commands

| Command | Palette Title | Description |
|---|---|---|
| `autopatch.scanWorkspace` | `AutoPatch: Scan Entire Workspace for Bugs` | Ingests workspace files, runs detection, and highlights bugs in code |
| `autopatch.scanActiveFile` | `AutoPatch: Scan Active File` | Quick inspection of the currently focused document |
| `autopatch.showBugReport` | `AutoPatch: Show Bug Report & Verified Patch` | Opens the rich native webview panel with diffs and causal evidence |
| `autopatch.applyPatch` | `AutoPatch: Apply Verified Patch` | Applies the verified replacement snippet directly into the open editor |
| `autopatch.openDashboard` | `AutoPatch: Open Web Remediation Dashboard` | Opens the web dashboard or standalone HTML report |

---

## Configuration Settings

Access settings via `Settings` -> `Extensions` -> `AutoPatch`:

- `autopatch.serverUrl` *(string, default: `http://127.0.0.1:8000`)*: URL of the running AutoPatch backend engine.
- `autopatch.apiToken` *(string, default: `dev_token_user_developer`)*: Bearer token for authenticated API requests.
- `autopatch.scanOnSave` *(boolean, default: `false`)*: Automatically trigger an inspection whenever an editor file is saved.
- `autopatch.concurrencyLimit` *(number, default: `3`)*: Maximum parallel bug repair pipelines.

---

## License

Apache-2.0
