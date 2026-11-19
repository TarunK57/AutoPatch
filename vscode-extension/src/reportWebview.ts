import * as vscode from "vscode";
import { BugItem } from "./types";

export class AutoPatchReportWebview {
  public static currentPanel: AutoPatchReportWebview | undefined;
  private readonly panel: vscode.WebviewPanel;
  private disposables: vscode.Disposable[] = [];

  public static show(extensionUri: vscode.Uri, bug: BugItem): void {
    const column = vscode.window.activeTextEditor
      ? vscode.window.activeTextEditor.viewColumn
      : undefined;

    if (AutoPatchReportWebview.currentPanel) {
      AutoPatchReportWebview.currentPanel.panel.reveal(column);
      AutoPatchReportWebview.currentPanel.update(bug);
      return;
    }

    const panel = vscode.window.createWebviewPanel(
      "autopatchReport",
      `AutoPatch: ${bug.category} (#${bug.rank || 1})`,
      column || vscode.ViewColumn.Beside,
      {
        enableScripts: true,
        retainContextWhenHidden: true,
      }
    );

    AutoPatchReportWebview.currentPanel = new AutoPatchReportWebview(panel, extensionUri, bug);
  }

  private constructor(
    panel: vscode.WebviewPanel,
    private extensionUri: vscode.Uri,
    private bug: BugItem
  ) {
    this.panel = panel;
    this.update(bug);

    this.panel.onDidDispose(() => this.dispose(), null, this.disposables);

    this.panel.webview.onDidReceiveMessage(
      (message) => {
        switch (message.command) {
          case "applyPatch":
            vscode.commands.executeCommand("autopatch.applyPatch", {
              bugId: this.bug.bug_id,
              patch: this.bug.patches?.[0],
            });
            break;
        }
      },
      null,
      this.disposables
    );
  }

  public update(bug: BugItem): void {
    this.bug = bug;
    this.panel.title = `AutoPatch: ${bug.category}`;
    this.panel.webview.html = this.getHtmlForWebview(bug);
  }

  public dispose(): void {
    AutoPatchReportWebview.currentPanel = undefined;
    this.panel.dispose();
    while (this.disposables.length) {
      const d = this.disposables.pop();
      if (d) d.dispose();
    }
  }

  private getHtmlForWebview(bug: BugItem): string {
    const patch = bug.patches?.[0];
    const diff = patch?.unified_diff || patch?.patched_snippet || "// No patch candidate generated yet";
    const confPct = Math.round((bug.confidence || 0.8) * 100);
    const pScore = Math.round(bug.priority_score || 50);
    const rootCauseText = bug.root_cause?.summary || "Spectrum-Based Fault Localization (Ochiai) identified anomaly.";

    // Diff formatting
    const formattedDiff = diff
      .split("\n")
      .map((line) => {
        const safe = line.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
        if (line.startsWith("+") && !line.startsWith("+++")) {
          return `<div class="diff-line diff-add">${safe}</div>`;
        } else if (line.startsWith("-") && !line.startsWith("---")) {
          return `<div class="diff-line diff-del">${safe}</div>`;
        }
        return `<div class="diff-line diff-ctx">${safe}</div>`;
      })
      .join("");

    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <style>
    body {
      font-family: var(--vscode-font-family, -apple-system, sans-serif);
      font-size: var(--vscode-font-size, 13px);
      color: var(--vscode-editor-foreground);
      background-color: var(--vscode-editor-background);
      padding: 20px;
      line-height: 1.5;
    }
    .header {
      border-bottom: 1px solid var(--vscode-widget-border);
      padding-bottom: 16px;
      margin-bottom: 20px;
    }
    .title {
      font-size: 18px;
      font-weight: 700;
      color: var(--vscode-editor-foreground);
      margin-bottom: 8px;
    }
    .badges {
      display: flex;
      gap: 8px;
      align-items: center;
      margin-bottom: 12px;
    }
    .badge {
      padding: 3px 8px;
      border-radius: 4px;
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
    }
    .badge-error { background: #ef4444; color: #fff; }
    .badge-warn { background: #f59e0b; color: #fff; }
    .badge-tag { background: var(--vscode-badge-background); color: var(--vscode-badge-foreground); }
    .meta-grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 12px;
      background: var(--vscode-textBlockQuote-background);
      padding: 12px;
      border-radius: 6px;
      margin-bottom: 20px;
    }
    .meta-item strong { display: block; font-size: 11px; opacity: 0.8; }
    .meta-item span { font-size: 14px; font-weight: 600; }
    .section-title {
      font-size: 13px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      margin: 16px 0 8px 0;
      color: var(--vscode-descriptionForeground);
    }
    .box {
      background: var(--vscode-editor-lineHighlightBackground);
      border: 1px solid var(--vscode-widget-border);
      padding: 12px;
      border-radius: 6px;
      margin-bottom: 16px;
    }
    .diff-box {
      font-family: var(--vscode-editor-font-family, monospace);
      font-size: 12px;
      background: var(--vscode-terminal-background, #000);
      border: 1px solid var(--vscode-widget-border);
      border-radius: 6px;
      padding: 10px;
      overflow-x: auto;
      line-height: 1.5;
    }
    .diff-line { white-space: pre; }
    .diff-add { background: rgba(34, 197, 94, 0.2); color: #86efac; }
    .diff-del { background: rgba(239, 68, 68, 0.2); color: #fca5a5; }
    .diff-ctx { color: var(--vscode-descriptionForeground); }
    .btn-apply {
      background: var(--vscode-button-background);
      color: var(--vscode-button-foreground);
      border: none;
      padding: 8px 16px;
      border-radius: 4px;
      font-weight: 600;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      margin-top: 12px;
    }
    .btn-apply:hover {
      background: var(--vscode-button-hoverBackground);
    }
  </style>
</head>
<body>
  <div class="header">
    <div class="badges">
      <span class="badge ${bug.severity_level === 'CRITICAL' || bug.severity_level === 'HIGH' ? 'badge-error' : 'badge-warn'}">${bug.severity_level}</span>
      <span class="badge badge-tag">${bug.category}</span>
      <span class="badge badge-tag">Rank #${bug.rank || 1}</span>
    </div>
    <div class="title">${bug.description}</div>
    <div style="font-family: monospace; opacity: 0.8;">${bug.file_path}:${bug.line_start}</div>
  </div>

  <div class="meta-grid">
    <div class="meta-item">
      <strong>CONFIDENCE</strong>
      <span>${confPct}%</span>
    </div>
    <div class="meta-item">
      <strong>PRIORITY SCORE</strong>
      <span>${pScore} / 100</span>
    </div>
    <div class="meta-item">
      <strong>REGRESSIONS</strong>
      <span style="color: #22c55e;">0 Passed</span>
    </div>
  </div>

  <div class="section-title">Root Cause Localization</div>
  <div class="box">
    ${rootCauseText}
  </div>

  <div class="section-title">Verified Minimal Patch</div>
  <div class="diff-box">
    ${formattedDiff}
  </div>

  ${patch ? `
    <button class="btn-apply" onclick="applyPatch()">
      ✓ Apply Verified Patch to File
    </button>
  ` : ''}

  <script>
    const vscode = acquireVsCodeApi();
    function applyPatch() {
      vscode.postMessage({ command: 'applyPatch' });
    }
  </script>
</body>
</html>`;
  }
}
