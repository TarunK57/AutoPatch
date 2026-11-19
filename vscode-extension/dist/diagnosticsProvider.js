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
exports.AutoPatchDiagnosticsManager = void 0;
const vscode = __importStar(require("vscode"));
const path = __importStar(require("path"));
class AutoPatchDiagnosticsManager {
    diagnosticCollection;
    bugsByFile = new Map();
    allBugs = new Map();
    constructor() {
        this.diagnosticCollection = vscode.languages.createDiagnosticCollection("autopatch");
    }
    get collection() {
        return this.diagnosticCollection;
    }
    getBug(bugId) {
        return this.allBugs.get(bugId);
    }
    getBugsForFile(filePath) {
        return this.bugsByFile.get(filePath) || [];
    }
    updateDiagnostics(workspaceRoot, bugs) {
        this.diagnosticCollection.clear();
        this.bugsByFile.clear();
        this.allBugs.clear();
        const diagnosticsByUri = new Map();
        for (const bug of bugs) {
            this.allBugs.set(bug.bug_id, bug);
            // Resolve absolute file path
            const absPath = path.isAbsolute(bug.file_path)
                ? bug.file_path
                : path.join(workspaceRoot, bug.file_path);
            if (!this.bugsByFile.has(absPath)) {
                this.bugsByFile.set(absPath, []);
            }
            this.bugsByFile.get(absPath).push(bug);
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
            diagnosticsByUri.get(uri.fsPath).push(diagnostic);
        }
        for (const [fsPath, diags] of diagnosticsByUri.entries()) {
            this.diagnosticCollection.set(vscode.Uri.file(fsPath), diags);
        }
    }
    clear() {
        this.diagnosticCollection.clear();
        this.bugsByFile.clear();
        this.allBugs.clear();
    }
    mapSeverity(level) {
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
    dispose() {
        this.diagnosticCollection.dispose();
    }
}
exports.AutoPatchDiagnosticsManager = AutoPatchDiagnosticsManager;
//# sourceMappingURL=diagnosticsProvider.js.map