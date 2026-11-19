import * as vscode from "vscode";
import * as http from "http";
import * as https from "https";
import { URL } from "url";
import { BugItem, ProjectResponse, ScanJobResponse } from "./types";

export class AutoPatchApiClient {
  private get serverUrl(): string {
    const config = vscode.workspace.getConfiguration("autopatch");
    return config.get<string>("serverUrl", "http://127.0.0.1:8000").replace(/\/$/, "");
  }

  private get apiToken(): string {
    const config = vscode.workspace.getConfiguration("autopatch");
    return config.get<string>("apiToken", "dev_token_user_developer");
  }

  private async request<T>(
    path: string,
    method: "GET" | "POST" | "DELETE" = "GET",
    body?: any,
    contentType: string = "application/json"
  ): Promise<T> {
    const targetUrl = new URL(`${this.serverUrl}/api/v1${path}`);
    const isHttps = targetUrl.protocol === "https:";
    const transport = isHttps ? https : http;

    return new Promise<T>((resolve, reject) => {
      const headers: Record<string, string> = {
        Authorization: `Bearer ${this.apiToken}`,
      };

      let payload: Buffer | null = null;
      if (body) {
        if (Buffer.isBuffer(body)) {
          payload = body;
          headers["Content-Type"] = contentType;
          headers["Content-Length"] = String(body.length);
        } else if (typeof body === "string") {
          payload = Buffer.from(body);
          headers["Content-Type"] = contentType;
          headers["Content-Length"] = String(payload.length);
        } else {
          payload = Buffer.from(JSON.stringify(body));
          headers["Content-Type"] = "application/json";
          headers["Content-Length"] = String(payload.length);
        }
      }

      const req = transport.request(
        targetUrl,
        {
          method,
          headers,
          timeout: 60000,
        },
        (res) => {
          let data = "";
          res.on("data", (chunk) => (data += chunk));
          res.on("end", () => {
            if (res.statusCode && res.statusCode >= 200 && res.statusCode < 300) {
              try {
                const parsed = JSON.parse(data);
                resolve(parsed as T);
              } catch {
                resolve(data as unknown as T);
              }
            } else {
              try {
                const errJson = JSON.parse(data);
                reject(new Error(errJson.detail || `Server returned error ${res.statusCode}`));
              } catch {
                reject(new Error(`Server returned error ${res.statusCode}: ${data}`));
              }
            }
          });
        }
      );

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

  public async createProjectFromPath(name: string, folderPath: string): Promise<ProjectResponse> {
    return this.request<ProjectResponse>("/projects", "POST", {
      name,
      github_url: folderPath,
    });
  }

  public async startScan(projectId: string, concurrency: number = 3): Promise<ScanJobResponse> {
    return this.request<ScanJobResponse>(`/projects/${projectId}/scan`, "POST", {
      concurrency_limit: concurrency,
    });
  }

  public async getJobStatus(jobId: string): Promise<ScanJobResponse> {
    return this.request<ScanJobResponse>(`/jobs/${jobId}`, "GET");
  }

  public async listBugs(projectId: string): Promise<BugItem[]> {
    const res = await this.request<{ bugs: BugItem[] }>(`/projects/${projectId}/bugs`, "GET");
    return res.bugs || [];
  }

  public async getBugDetail(bugId: string): Promise<any> {
    return this.request<any>(`/bugs/${encodeURIComponent(bugId)}`, "GET");
  }

  public async submitDecision(
    bugId: string,
    decision: "APPROVED" | "REJECTED" | "NEEDS_REVIEW",
    comment: string = ""
  ): Promise<any> {
    return this.request<any>(`/bugs/${encodeURIComponent(bugId)}/decision`, "POST", {
      decision,
      comment,
    });
  }

  public getReportWebUrl(projectId: string): string {
    return `${this.serverUrl}/api/v1/projects/${projectId}/report?format=html`;
  }
}
