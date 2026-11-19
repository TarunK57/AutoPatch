import * as vscode from "vscode";
import { AutoPatchDiagnosticsManager } from "./diagnosticsProvider";
import { BugItem } from "./types";

export class AutoPatchCodeActionProvider implements vscode.CodeActionProvider {
  public static readonly providedCodeActionKinds = [
    vscode.CodeActionKind.QuickFix,
  ];

  constructor(private diagnosticsManager: AutoPatchDiagnosticsManager) {}

  public provideCodeActions(
    document: vscode.TextDocument,
    range: vscode.Range | vscode.Selection,
    context: vscode.CodeActionContext,
    token: vscode.CancellationToken
  ): vscode.CodeAction[] {
    const actions: vscode.CodeAction[] = [];

    // Filter diagnostics that originate from AutoPatch
    const autopatchDiags = context.diagnostics.filter(
      (d) => d.source === "AutoPatch"
    );

    for (const diag of autopatchDiags) {
      let bugId: string | undefined;
      if (typeof diag.code === "object" && diag.code !== null && "value" in diag.code) {
        bugId = String(diag.code.value);
      } else if (typeof diag.code === "string") {
        bugId = diag.code;
      }

      if (!bugId) continue;
      const bug = this.diagnosticsManager.getBug(bugId);
      if (!bug) continue;

      // 1. Quick Fix: Apply Verified Patch
      if (bug.patches && bug.patches.length > 0) {
        const patch = bug.patches[0];
        const confPct = Math.round((patch.confidence || bug.confidence || 0.8) * 100);
        const actionTitle = `💡 AutoPatch: Apply verified patch (${confPct}% confidence)`;
        const fixAction = new vscode.CodeAction(actionTitle, vscode.CodeActionKind.QuickFix);
        fixAction.diagnostics = [diag];
        fixAction.isPreferred = true;

        // Command to apply the patch
        fixAction.command = {
          command: "autopatch.applyPatch",
          title: actionTitle,
          arguments: [{ bugId: bug.bug_id, patch }],
        };
        actions.push(fixAction);
      }

      // 2. Action: View Root Cause & BRT Evidence Panel
      const reportAction = new vscode.CodeAction(
        `🔍 AutoPatch: View Root Cause & BRT Evidence`,
        vscode.CodeActionKind.QuickFix
      );
      reportAction.diagnostics = [diag];
      reportAction.command = {
        command: "autopatch.showBugReport",
        title: "Show Bug Report",
        arguments: [{ bugId: bug.bug_id }],
      };
      actions.push(reportAction);
    }

    return actions;
  }
}
