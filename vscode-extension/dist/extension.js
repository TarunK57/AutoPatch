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
exports.activate = activate;
exports.deactivate = deactivate;
const vscode = __importStar(require("vscode"));
const path = __importStar(require("path"));
const apiClient_1 = require("./apiClient");
const diagnosticsProvider_1 = require("./diagnosticsProvider");
const codeActionProvider_1 = require("./codeActionProvider");
const reportWebview_1 = require("./reportWebview");
let currentProjectId = null;
let statusBarItem;
function activate(context) {
    const apiClient = new apiClient_1.AutoPatchApiClient();
    const diagnosticsManager = new diagnosticsProvider_1.AutoPatchDiagnosticsManager();
    // Status Bar Item
    statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
    statusBarItem.text = "$(shield) AutoPatch: Ready";
    statusBarItem.tooltip = "AutoPatch Autonomous Bug Repair Engine";
    statusBarItem.command = "autopatch.scanWorkspace";
    statusBarItem.show();
    context.subscriptions.push(statusBarItem);
    // Register Code Action Provider for Python, JS, and TS
    const selector = [
        { language: "python", scheme: "file" },
        { language: "javascript", scheme: "file" },
        { language: "typescript", scheme: "file" },
        { language: "javascriptreact", scheme: "file" },
        { language: "typescriptreact", scheme: "file" },
    ];
    context.subscriptions.push(vscode.languages.registerCodeActionsProvider(selector, new codeActionProvider_1.AutoPatchCodeActionProvider(diagnosticsManager), {
        providedCodeActionKinds: codeActionProvider_1.AutoPatchCodeActionProvider.providedCodeActionKinds,
    }));
    // Command 1: Scan Workspace
    const scanWorkspaceCmd = vscode.commands.registerCommand("autopatch.scanWorkspace", async () => {
        const workspaceFolders = vscode.workspace.workspaceFolders;
        if (!workspaceFolders || workspaceFolders.length === 0) {
            vscode.window.showWarningMessage("AutoPatch: No open workspace folder to scan.");
            return;
        }
        const rootPath = workspaceFolders[0].uri.fsPath;
        const projectName = path.basename(rootPath);
        statusBarItem.text = "$(sync~spin) AutoPatch: Ingesting & Scanning...";
        statusBarItem.tooltip = "Autonomous inspection, SBFL localization, and patch verification in progress";
        try {
            await vscode.window.withProgress({
                location: vscode.ProgressLocation.Notification,
                title: `AutoPatch: Inspecting ${projectName}`,
                cancellable: false,
            }, async (progress) => {
                progress.report({ message: "Registering project with backend engine..." });
                const project = await apiClient.createProjectFromPath(projectName, rootPath);
                currentProjectId = project.project_id;
                progress.report({ message: "Running detection pipeline and SBFL localization..." });
                const config = vscode.workspace.getConfiguration("autopatch");
                const concurrency = config.get("concurrencyLimit", 3);
                const job = await apiClient.startScan(project.project_id, concurrency);
                // Poll for job completion
                let finished = false;
                let attempts = 0;
                while (!finished && attempts < 120) {
                    await new Promise((r) => setTimeout(r, 1000));
                    attempts++;
                    const status = await apiClient.getJobStatus(job.job_id);
                    progress.report({
                        message: `Analyzing bugs (${status.completed_bugs}/${status.total_bugs || "?"})...`,
                    });
                    if (status.status === "COMPLETED" || status.status === "COMPLETED_PARTIAL") {
                        finished = true;
                    }
                    else if (status.status === "FAILED" || status.status === "CANCELLED") {
                        throw new Error(`Job ended with status: ${status.status}`);
                    }
                }
                progress.report({ message: "Rendering diagnostics..." });
                const bugs = await apiClient.listBugs(project.project_id);
                diagnosticsManager.updateDiagnostics(rootPath, bugs);
                const bugCount = bugs.length;
                statusBarItem.text = `$(shield) AutoPatch: ${bugCount} bug${bugCount === 1 ? "" : "s"} found`;
                statusBarItem.tooltip = `AutoPatch identified ${bugCount} verified flaws in ${projectName}`;
                vscode.window.showInformationMessage(`AutoPatch: Scan completed. Found ${bugCount} defect${bugCount === 1 ? "" : "s"} with verified patches.`, "Open Web Report").then((action) => {
                    if (action === "Open Web Report" && currentProjectId) {
                        vscode.env.openExternal(vscode.Uri.parse(apiClient.getReportWebUrl(currentProjectId)));
                    }
                });
            });
        }
        catch (err) {
            statusBarItem.text = "$(alert) AutoPatch: Scan Failed";
            vscode.window.showErrorMessage(`AutoPatch Error: ${err.message}`);
        }
    });
    context.subscriptions.push(scanWorkspaceCmd);
    // Command 2: Scan Active File
    const scanActiveFileCmd = vscode.commands.registerCommand("autopatch.scanActiveFile", async () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor) {
            vscode.window.showWarningMessage("AutoPatch: No active editor to scan.");
            return;
        }
        vscode.commands.executeCommand("autopatch.scanWorkspace");
    });
    context.subscriptions.push(scanActiveFileCmd);
    // Command 3: Show Bug Report Webview
    const showBugReportCmd = vscode.commands.registerCommand("autopatch.showBugReport", async (args) => {
        let bug;
        if (args?.bugId) {
            bug = diagnosticsManager.getBug(args.bugId);
        }
        if (!bug) {
            const editor = vscode.window.activeTextEditor;
            if (editor) {
                const bugs = diagnosticsManager.getBugsForFile(editor.document.uri.fsPath);
                if (bugs.length > 0) {
                    bug = bugs[0];
                }
            }
        }
        if (!bug) {
            vscode.window.showInformationMessage("AutoPatch: No defect selected or found at current location.");
            return;
        }
        reportWebview_1.AutoPatchReportWebview.show(context.extensionUri, bug);
    });
    context.subscriptions.push(showBugReportCmd);
    // Command 4: Apply Verified Patch
    const applyPatchCmd = vscode.commands.registerCommand("autopatch.applyPatch", async (args) => {
        const bug = diagnosticsManager.getBug(args.bugId);
        const patch = args.patch || bug?.patches?.[0];
        if (!bug || !patch) {
            vscode.window.showErrorMessage("AutoPatch: No patch candidate found for this bug.");
            return;
        }
        const workspaceFolders = vscode.workspace.workspaceFolders;
        const rootPath = workspaceFolders ? workspaceFolders[0].uri.fsPath : "";
        const targetAbsPath = path.isAbsolute(patch.file)
            ? patch.file
            : path.join(rootPath, patch.file);
        try {
            const uri = vscode.Uri.file(targetAbsPath);
            const document = await vscode.workspace.openTextDocument(uri);
            const editor = await vscode.window.showTextDocument(document);
            const currentText = document.getText();
            const orig = patch.original_snippet;
            const replacement = patch.patched_snippet;
            if (currentText.includes(orig)) {
                const startIdx = currentText.indexOf(orig);
                const startPos = document.positionAt(startIdx);
                const endPos = document.positionAt(startIdx + orig.length);
                const range = new vscode.Range(startPos, endPos);
                const edit = new vscode.WorkspaceEdit();
                edit.replace(uri, range, replacement);
                await vscode.workspace.applyEdit(edit);
                await document.save();
                // Inform backend of approval
                apiClient.submitDecision(bug.bug_id, "APPROVED", "Accepted via IDE Extension").catch(() => { });
                vscode.window.showInformationMessage(`AutoPatch: Successfully applied verified fix to ${path.basename(targetAbsPath)}!`);
            }
            else {
                vscode.window.showWarningMessage("AutoPatch: Target code snippet was modified since scan. Please review diff in Web Report.", "Open Web Report").then((action) => {
                    if (action === "Open Web Report" && currentProjectId) {
                        vscode.env.openExternal(vscode.Uri.parse(apiClient.getReportWebUrl(currentProjectId)));
                    }
                });
            }
        }
        catch (err) {
            vscode.window.showErrorMessage(`AutoPatch: Failed to apply patch: ${err.message}`);
        }
    });
    context.subscriptions.push(applyPatchCmd);
    // Command 5: Open Web Dashboard
    const openDashboardCmd = vscode.commands.registerCommand("autopatch.openDashboard", () => {
        if (currentProjectId) {
            vscode.env.openExternal(vscode.Uri.parse(apiClient.getReportWebUrl(currentProjectId)));
        }
        else {
            vscode.env.openExternal(vscode.Uri.parse("http://localhost:3000"));
        }
    });
    context.subscriptions.push(openDashboardCmd);
    // Optional: Scan on save
    context.subscriptions.push(vscode.workspace.onDidSaveTextDocument((doc) => {
        const config = vscode.workspace.getConfiguration("autopatch");
        if (config.get("scanOnSave", false)) {
            vscode.commands.executeCommand("autopatch.scanActiveFile");
        }
    }));
    context.subscriptions.push(diagnosticsManager);
}
function deactivate() {
    if (statusBarItem) {
        statusBarItem.dispose();
    }
}
//# sourceMappingURL=extension.js.map