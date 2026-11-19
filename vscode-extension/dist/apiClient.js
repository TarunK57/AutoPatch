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
exports.AutoPatchApiClient = void 0;
const vscode = __importStar(require("vscode"));
const http = __importStar(require("http"));
const https = __importStar(require("https"));
const url_1 = require("url");
class AutoPatchApiClient {
    get serverUrl() {
        const config = vscode.workspace.getConfiguration("autopatch");
        return config.get("serverUrl", "http://127.0.0.1:8000").replace(/\/$/, "");
    }
    get apiToken() {
        const config = vscode.workspace.getConfiguration("autopatch");
        return config.get("apiToken", "dev_token_user_developer");
    }
    async request(path, method = "GET", body, contentType = "application/json") {
        const targetUrl = new url_1.URL(`${this.serverUrl}/api/v1${path}`);
        const isHttps = targetUrl.protocol === "https:";
        const transport = isHttps ? https : http;
        return new Promise((resolve, reject) => {
            const headers = {
                Authorization: `Bearer ${this.apiToken}`,
            };
            let payload = null;
            if (body) {
                if (Buffer.isBuffer(body)) {
                    payload = body;
                    headers["Content-Type"] = contentType;
                    headers["Content-Length"] = String(body.length);
                }
                else if (typeof body === "string") {
                    payload = Buffer.from(body);
                    headers["Content-Type"] = contentType;
                    headers["Content-Length"] = String(payload.length);
                }
                else {
                    payload = Buffer.from(JSON.stringify(body));
                    headers["Content-Type"] = "application/json";
                    headers["Content-Length"] = String(payload.length);
                }
            }
            const req = transport.request(targetUrl, {
                method,
                headers,
                timeout: 60000,
            }, (res) => {
                let data = "";
                res.on("data", (chunk) => (data += chunk));
                res.on("end", () => {
                    if (res.statusCode && res.statusCode >= 200 && res.statusCode < 300) {
                        try {
                            const parsed = JSON.parse(data);
                            resolve(parsed);
                        }
                        catch {
                            resolve(data);
                        }
                    }
                    else {
                        try {
                            const errJson = JSON.parse(data);
                            reject(new Error(errJson.detail || `Server returned error ${res.statusCode}`));
                        }
                        catch {
                            reject(new Error(`Server returned error ${res.statusCode}: ${data}`));
                        }
                    }
                });
            });
            req.on("error", (err) => {
                reject(new Error(`Failed to reach AutoPatch server at ${this.serverUrl}: ${err.message}`));
            });
            req.on("timeout", () => {
                req.destroy();
                reject(new Error(`Request to AutoPatch server timed out after 60s.`));
            });
            if (payload) {
                req.write(payload);
            }
            req.end();
        });
    }
    async createProjectFromPath(name, folderPath) {
        return this.request("/projects", "POST", {
            name,
            github_url: folderPath,
        });
    }
    async startScan(projectId, concurrency = 3) {
        return this.request(`/projects/${projectId}/scan`, "POST", {
            concurrency_limit: concurrency,
        });
    }
    async getJobStatus(jobId) {
        return this.request(`/jobs/${jobId}`, "GET");
    }
    async listBugs(projectId) {
        const res = await this.request(`/projects/${projectId}/bugs`, "GET");
        return res.bugs || [];
    }
    async getBugDetail(bugId) {
        return this.request(`/bugs/${encodeURIComponent(bugId)}`, "GET");
    }
    async submitDecision(bugId, decision, comment = "") {
        return this.request(`/bugs/${encodeURIComponent(bugId)}/decision`, "POST", {
            decision,
            comment,
        });
    }
    getReportWebUrl(projectId) {
        return `${this.serverUrl}/api/v1/projects/${projectId}/report?format=html`;
    }
}
exports.AutoPatchApiClient = AutoPatchApiClient;
//# sourceMappingURL=apiClient.js.map