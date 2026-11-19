"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.AutoPatchCodeActionProvider = void 0;
const vscode = __importStar(require("vscode"));
class AutoPatchCodeActionProvider {
    diagnosticsManager;
    static providedCodeActionKinds = [
        vscode.CodeActionKind.QuickFix,
    ];
    constructor(diagnosticsManager) {
        this.diagnosticsManager = diagnosticsManager;
    }
    provideCodeActions(document, range, context, token) {
        const actions = [];
        // Filter diagnostics that originate from AutoPatch
        const autopatchDiags = context.diagnostics.filter((d) => d.source === "AutoPatch");
        for (const diag of autopatchDiags) {
            let bugId;
            if (typeof diag.code === "object" && diag.code !== null && "value" in diag.code) {
                bugId = String(diag.code.value);
            }
            else if (typeof diag.code === "string") {
                bugId = diag.code;
            }
            if (!bugId)
                continue;
            const bug = this.diagnosticsManager.getBug(bugId);
            if (!bug)
                continue;
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
            const reportAction = new vscode.CodeAction(`🔍 AutoPatch: View Root Cause & BRT Evidence`, vscode.CodeActionKind.QuickFix);
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
exports.AutoPatchCodeActionProvider = AutoPatchCodeActionProvider;
//# sourceMappingURL=codeActionProvider.js.map