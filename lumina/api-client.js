/**
 * LuminaAI AutoPatch - Client API Integration Layer
 * 
 * Provides live connectivity to the AutoPatch FastAPI backend with Server-Sent Events (SSE),
 * durable state tracking, human-in-the-loop decision recording, and explicit
 * distinction between live connected mode and offline demo mode.
 */

const API_CONFIG = {
  baseUrl: window.AUTOPATCH_API_URL || 'http://localhost:8000/api/v1',
  healthUrl: window.AUTOPATCH_HEALTH_URL || 'http://localhost:8000/health',
  authToken: window.AUTOPATCH_AUTH_TOKEN || 'dev_token_user_developer',
  timeoutMs: 4000,
};

class AutoPatchClient {
  constructor(config = {}) {
    this.config = { ...API_CONFIG, ...config };
    this._isOnline = null;
    this._activeEventSource = null;
  }

  get headers() {
    return {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${this.config.authToken}`,
    };
  }

  /**
   * Probes backend health endpoint with timeout.
   * @returns {Promise<boolean>}
   */
  async checkHealth() {
    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), this.config.timeoutMs);
      const res = await fetch(this.config.healthUrl, {
        method: 'GET',
        signal: controller.signal,
      });
      clearTimeout(timeout);
      this._isOnline = res.ok;
      return res.ok;
    } catch (err) {
      this._isOnline = false;
      return false;
    }
  }

  /**
   * Renders the backend connectivity pill into the target DOM element.
   */
  async renderStatusPill(containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;

    const online = await this.checkHealth();
    if (online) {
      container.innerHTML = `
        <div class="backend-pill online" title="Connected to AutoPatch Engine at ${this.config.baseUrl}">
          <span class="status-dot"></span>
          <span>LIVE BACKEND</span>
        </div>
      `;
    } else {
      container.innerHTML = `
        <div class="backend-pill offline" title="Backend offline at http://localhost:8000. Start backend to run real live scans and sandbox verifications.">
          <span class="status-dot"></span>
          <span>DEMO / OFFLINE MODE</span>
        </div>
      `;
    }
  }

  /**
   * Creates or registers a code project.
   */
  async createProject(name, githubUrl = null) {
    if (!this._isOnline) {
      throw new Error('Backend is offline. Cannot create live project.');
    }
    const res = await fetch(`${this.config.baseUrl}/projects`, {
      method: 'POST',
      headers: this.headers,
      body: JSON.stringify({ name, github_url: githubUrl }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `Project creation failed: ${res.status}`);
    }
    return await res.json();
  }

  /**
   * Lists all projects owned by current user.
   */
  async listProjects() {
    if (!this._isOnline) return [];
    const res = await fetch(`${this.config.baseUrl}/projects`, {
      headers: this.headers,
    });
    if (!res.ok) return [];
    return await res.json();
  }

  /**
   * Starts a new scan job for a project.
   */
  async startScanJob(projectId) {
    if (!this._isOnline) {
      throw new Error('Backend is offline. Cannot initiate autonomous scan job.');
    }
    const res = await fetch(`${this.config.baseUrl}/jobs`, {
      method: 'POST',
      headers: this.headers,
      body: JSON.stringify({ project_id: projectId }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `Failed to start scan job: ${res.status}`);
    }
    return await res.json();
  }

  /**
   * Subscribes to real-time Server-Sent Events (SSE) for a scan job.
   */
  streamJobEvents(jobId, onEvent, onError, onComplete) {
    if (this._activeEventSource) {
      this._activeEventSource.close();
    }

    const url = `${this.config.baseUrl}/jobs/${jobId}/events`;
    const es = new EventSource(url);
    this._activeEventSource = es;

    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        if (onEvent) onEvent(data);
        if (data.event === 'JOB_COMPLETED' || data.event === 'JOB_FAILED' || data.event === 'JOB_CANCELLED') {
          es.close();
          this._activeEventSource = null;
          if (onComplete) onComplete(data);
        }
      } catch (err) {
        console.warn('Error parsing SSE event payload:', err);
      }
    };

    es.onerror = (err) => {
      console.warn('SSE stream connection issue:', err);
      if (onError) onError(err);
    };

    return es;
  }

  /**
   * Lists ranked bugs for a project with optional filters.
   */
  async listBugs(projectId, severity = null, status = null) {
    let url = `${this.config.baseUrl}/projects/${projectId}/bugs`;
    const params = new URLSearchParams();
    if (severity) params.set('severity', severity);
    if (status) params.set('status', status);
    if (params.toString()) url += `?${params.toString()}`;

    const res = await fetch(url, { headers: this.headers });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `Failed to fetch ranked bugs: ${res.status}`);
    }
    return await res.json();
  }

  /**
   * Fetches detailed bug report and candidate patch dossiers.
   */
  async getBugDetails(projectId, bugId) {
    const res = await fetch(`${this.config.baseUrl}/projects/${projectId}/bugs/${encodeURIComponent(bugId)}`, {
      headers: this.headers,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `Bug details fetch failed: ${res.status}`);
    }
    return await res.json();
  }

  /**
   * Records explicit human approval or rejection decision.
   */
  async recordDecision(projectId, bugId, decision) {
    if (!this._isOnline) {
      throw new Error('Backend is offline. Live human approval cannot be submitted without a running server.');
    }
    const res = await fetch(`${this.config.baseUrl}/projects/${projectId}/bugs/${encodeURIComponent(bugId)}/decision`, {
      method: 'POST',
      headers: this.headers,
      body: JSON.stringify(decision),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `Failed to record patch decision: ${res.status}`);
    }
    return await res.json();
  }

  /**
   * Fetches dashboard telemetry and cost observability data.
   */
  async getDashboardMetrics() {
    if (!this._isOnline) return null;
    try {
      const res = await fetch(`${this.config.baseUrl}/observability/dashboard`, {
        headers: this.headers,
      });
      if (!res.ok) return null;
      return await res.json();
    } catch {
      return null;
    }
  }
}

// Global singleton instance
window.autopatch = new AutoPatchClient();
