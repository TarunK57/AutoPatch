import * as vscode from "vscode";
import * as path from "path";
import { BugItem, SeverityLevel } from "./types";

export class AutoPatchDiagnosticsManager {
  private diagnosticCollection: vscode.DiagnosticCollection;
  private bugsByFile: Map<string, BugItem[]> = new Map();
  private allBugs: Map<string, BugItem> = new Map();

  constructor() {
    this.diagnosticCollection = vscode.languages.createDiagnosticCollection("autopatch");
  }

  public get collection(): vscode.DiagnosticCollection {
    return this.diagnosticCollection;
  }

  public getBug(bugId: string): BugItem | undefined {
    return this.allBugs.get(bugId);
  }

  public getBugsForFile(filePath: string): BugItem[] {
    return this.bugsByFile.get(filePath) || [];
  }

  public updateDiagnostics(workspaceRoot: string, bugs: BugItem[]): void {
    this.diagnosticCollection.clear();
    this.bugsByFile.clear();
    this.allBugs.clear();

    const diagnosticsByUri: Map<string, vscode.Diagnostic[]> = new Map();

    for (const bug of bugs) {
      this.allBugs.set(bug.bug_id, bug);

      // Resolve absolute file path
      const absPath = path.isAbsolute(bug.file_path)
        ? bug.file_path
        : path.join(workspaceRoot, bug.file_path);

      if (!this.bugsByFile.has(absPath)) {
        this.bugsByFile.set(absPath, []);
      }
      this.bugsByFile.get(absPath)!.push(bug);

      const uri = vscode.Uri.file(absPath);
      const lineStart = Math.max(0, (bug.line_start || 1) - 1);
      const lineEnd = Math.max(lineStart, (bug.line_end || bug.line_start || 1) - 1);
      const range = new vscode.Range(lineStart, 0, lineEnd, 999);

      const severity = this.mapSeverity(bug.severity_level);
      const confPct = Math.round((bug.confidence || 0.8) * 100);
      const priority = Math.round(bug.priority_score || 50);

      const message = `[AutoPatch: ${bug.category}] ${bug.description}\nSeverity: ${bug.severity_level} | Confidence: ${confPct}% | Priority: ${priority}/100`;

      const diagnostic = new vscode.Diagnostic(range, message, severity);
      diagnostic.source = "AutoPatch";
      diagnostic.code = {
        value: bug.bug_id,
        target: vscode.Uri.parse(`command:autopatch.showBugReport?${encodeURIComponent(JSON.stringify({ bugId: bug.bug_id }))}`),
      };

      if (!diagnosticsByUri.has(uri.fsPath)) {
        diagnosticsByUri.set(uri.fsPath, []);
      }
      diagnosticsByUri.get(uri.fsPath)!.push(diagnostic);
    }

    for (const [fsPath, diags] of diagnosticsByUri.entries()) {
      this.diagnosticCollection.set(vscode.Uri.file(fsPath), diags);
    }
  }

  public clear(): void {
    this.diagnosticCollection.clear();
    this.bugsByFile.clear();
    this.allBugs.clear();
  }

  private mapSeverity(level: SeverityLevel): vscode.DiagnosticSeverity {
    switch (level) {
      case "CRITICAL":
      case "HIGH":
        return vscode.DiagnosticSeverity.Error;
      case "MEDIUM":
        return vscode.DiagnosticSeverity.Warning;
      case "LOW":
      case "STYLE":
      default:
        return vscode.DiagnosticSeverity.Information;
    }
  }

  public dispose(): void {
    this.diagnosticCollection.dispose();
  }
}
