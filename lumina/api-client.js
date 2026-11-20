/**
 * LuminaAI AutoPatch - Client API Integration Layer
 * 
 * Provides live connectivity to the AutoPatch FastAPI backend with Server-Sent Events (SSE),
 * durable state tracking, human-in-the-loop decision recording, and explicit
 * live SSE telemetry, and real human-in-the-loop decision recording.
 */

const defaultBaseUrl = (typeof window !== 'undefined' && window.location.port !== '3000' && window.location.origin && window.location.origin.startsWith('http'))
  ? `${window.location.origin}/api/v1`
  : 'http://localhost:8000/api/v1';

const defaultHealthUrl = (typeof window !== 'undefined' && window.location.port !== '3000' && window.location.origin && window.location.origin.startsWith('http'))
  ? `${window.location.origin}/health`
  : 'http://localhost:8000/health';

const API_CONFIG = {
  baseUrl: (typeof window !== 'undefined' && window.AUTOPATCH_API_URL) || defaultBaseUrl,
  healthUrl: (typeof window !== 'undefined' && window.AUTOPATCH_HEALTH_URL) || defaultHealthUrl,
  authToken: (typeof window !== 'undefined' && window.AUTOPATCH_AUTH_TOKEN) || 'dev_token_user_developer',
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
          <span>BACKEND OFFLINE</span>
        </div>
      `;
    }
  }

  /**
   * Creates or registers a code project.
   */
  async createProject(name, githubUrl = null, file = null) {
    if (this._isOnline === false) {
      throw new Error('Backend is offline. Cannot create live project.');
    }
    const token = localStorage.getItem('autopatch_gh_token');
    let res;
    if (file) {
      const formData = new FormData();
      formData.append('name', name);
      if (githubUrl) formData.append('github_url', githubUrl);
      if (token) formData.append('token', token);
      formData.append('file', file);
      const customHeaders = { 'Authorization': `Bearer ${this.config.authToken}` };
      if (token) customHeaders['x-github-token'] = token;
      res = await fetch(`${this.config.baseUrl}/projects`, {
        method: 'POST',
        headers: customHeaders,
        body: formData,
      });
    } else {
      const customHeaders = { ...this.headers };
      if (token) customHeaders['x-github-token'] = token;
      res = await fetch(`${this.config.baseUrl}/projects`, {
        method: 'POST',
        headers: customHeaders,
        body: JSON.stringify({ name, github_url: githubUrl, token: token }),
      });
    }
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `Project creation failed: ${res.status}`);
    }
    this._isOnline = true;
    return await res.json();
  }

  /**
   * Lists all projects owned by current user.
   */
  async listProjects() {
    try {
      const res = await fetch(`${this.config.baseUrl}/projects`, {
        headers: this.headers,
      });
      if (res.ok) {
        this._isOnline = true;
        return await res.json();
      }
      return [];
    } catch (e) {
      console.warn('listProjects fetch error:', e);
      return [];
    }
  }

  /**
   * Starts a new scan job for a project.
   */
  async startScanJob(projectId) {
    if (this._isOnline === false) {
      throw new Error('Backend is offline. Cannot initiate autonomous scan job.');
    }
    // Try primary project scan endpoint first
    let res = await fetch(`${this.config.baseUrl}/projects/${encodeURIComponent(projectId)}/scan`, {
      method: 'POST',
      headers: this.headers,
      body: JSON.stringify({}),
    });

    if (res.status === 404) {
      // Fallback to /jobs alias endpoint
      res = await fetch(`${this.config.baseUrl}/jobs`, {
        method: 'POST',
        headers: this.headers,
        body: JSON.stringify({ project_id: projectId }),
      });
    }

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

    const tokenParam = encodeURIComponent(this.config.authToken);
    const url = `${this.config.baseUrl}/jobs/${encodeURIComponent(jobId)}/events?token=${tokenParam}`;
    const es = new EventSource(url);
    this._activeEventSource = es;

    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        if (onEvent) onEvent(data);
        if (data.event === 'DONE' || data.event === 'JOB_COMPLETED' || data.event === 'JOB_FAILED' || data.event === 'JOB_CANCELLED') {
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
    if (this._isOnline === false) {
      throw new Error('Backend is offline. Live human approval cannot be submitted without a running server.');
    }
    const payload = {
      decision: decision.decision || decision.status,
      status: decision.status || decision.decision,
      patch_id: decision.patch_id,
      comment: decision.comment || '',
    };
    const res = await fetch(`${this.config.baseUrl}/projects/${projectId}/bugs/${encodeURIComponent(bugId)}/decision`, {
      method: 'POST',
      headers: this.headers,
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `Failed to record patch decision: ${res.status}`);
    }
    return await res.json();
  }

  /**
   * Triggers download of the complete codebase as a ZIP archive with all verified fixes.
   */
  async downloadPatchedZip(projectId, customFilename = null) {
    if (this._isOnline === false) {
      throw new Error('Backend is offline. Cannot download patched ZIP.');
    }
    const downloadUrl = `${this.config.baseUrl}/projects/${encodeURIComponent(projectId)}/download-zip`;
    const res = await fetch(downloadUrl, { headers: this.headers });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `Failed to download patched ZIP: ${res.status}`);
    }
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.style.display = 'none';
    a.href = url;
    a.download = customFilename || `autopatch_${projectId.slice(0, 8)}_patched.zip`;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => {
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    }, 2000);
    return true;
  }

  /**
   * Pushes remediation branch to remote git repository.
   */
  async pushRemediationBranch(projectId, branchName, githubToken = null, remoteUrl = null) {
    if (this._isOnline === false) {
      throw new Error('Backend is offline. Cannot push branch to remote repository.');
    }
    const payload = {
      branch_name: branchName,
      github_token: githubToken || localStorage.getItem('autopatch_gh_token') || null,
      remote_url: remoteUrl || null,
    };
    const res = await fetch(`${this.config.baseUrl}/projects/${encodeURIComponent(projectId)}/git/push`, {
      method: 'POST',
      headers: this.headers,
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `Failed to push branch: ${res.status}`);
    }
    return await res.json();
  }

  /**
   * Opens a GitHub pull request with formatted verification evidence table.
   */
  async openPullRequest(projectId, repoSlug, headBranch, baseBranch = 'main', title = null, githubToken = null) {
    if (this._isOnline === false) {
      throw new Error('Backend is offline. Cannot open pull request.');
    }
    const payload = {
      repo_slug: repoSlug,
      head_branch: headBranch,
      base_branch: baseBranch,
      title: title || null,
      github_token: githubToken || localStorage.getItem('autopatch_gh_token') || null,
    };
    const res = await fetch(`${this.config.baseUrl}/projects/${encodeURIComponent(projectId)}/git/pull-request`, {
      method: 'POST',
      headers: this.headers,
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `Failed to create pull request: ${res.status}`);
    }
    return await res.json();
  }

  /**
   * Fetches official GitHub OAuth configuration.
   */
  async getGitHubOAuthConfig() {
    try {
      const res = await fetch(`${this.config.baseUrl}/github/oauth/config`, { headers: this.headers });
      if (!res.ok) return { is_configured: false };
      return await res.json();
    } catch {
      return { is_configured: false };
    }
  }

  /**
   * Directly connects an official GitHub account handle without requiring a manual PAT.
   */
  async portalConnectGitHub(username, token = null) {
    const payload = {
      username: username,
      token: token || localStorage.getItem('autopatch_gh_token') || null,
    };
    const res = await fetch(`${this.config.baseUrl}/github/portal-connect`, {
      method: 'POST',
      headers: this.headers,
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `Failed to connect with GitHub portal: ${res.status}`);
    }
    return await res.json();
  }

  /**
   * Validates GitHub token or username and returns authenticated user profile.
   */
  async getGitHubUser(token = null, username = null) {
    const tok = token || localStorage.getItem('autopatch_gh_token');
    const params = new URLSearchParams();
    if (tok) params.set('token', tok);
    if (username) params.set('username', username);
    if (!tok && !username) return null;
    const url = `${this.config.baseUrl}/github/user?${params.toString()}`;
    const res = await fetch(url, { headers: this.headers });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || 'GitHub profile fetch failed');
    }
    return await res.json();
  }

  /**
   * Lists repositories for authenticated user or username.
   */
  async listGitHubRepos(token = null, username = null) {
    const tok = token || localStorage.getItem('autopatch_gh_token');
    const params = new URLSearchParams();
    if (tok) params.set('token', tok);
    if (username) params.set('username', username);
    const url = `${this.config.baseUrl}/github/repos?${params.toString()}`;
    const res = await fetch(url, { headers: this.headers });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || 'Failed to list GitHub repositories');
    }
    return await res.json();
  }

  /**
   * Fetches real live dashboard telemetry, KPIs, CWE breakdown, velocity points, and activity ledger.
   */
  async getDashboardMetrics(projectId = null) {
    if (this._isOnline === false) return null;
    try {
      const url = projectId
        ? `${this.config.baseUrl}/observability/dashboard?project_id=${encodeURIComponent(projectId)}`
        : `${this.config.baseUrl}/observability/dashboard`;
      const res = await fetch(url, { headers: this.headers });
      if (!res.ok) return null;
      return await res.json();
    } catch {
      return null;
    }
  }

  // ==========================================================================
  // Advanced Enterprise Features SDK Methods
  // ==========================================================================

  /**
   * 1. Predictive Bug Detection: Fetches predicted failure hazards and failure probabilities.
   */
  async getPredictiveAnalysis(projectId) {
    const res = await fetch(`${this.config.baseUrl}/projects/${encodeURIComponent(projectId)}/predictive-analysis`, {
      headers: this.headers,
    });
    if (!res.ok) throw new Error(`Predictive analysis failed: ${res.status}`);
    return await res.json();
  }

  /**
   * 2. Code Hotspot Detection: Cross-references Git churn and file complexity.
   */
  async getCodeHotspots(projectId, maxResults = 25) {
    const res = await fetch(`${this.config.baseUrl}/projects/${encodeURIComponent(projectId)}/hotspots?max_results=${maxResults}`, {
      headers: this.headers,
    });
    if (!res.ok) throw new Error(`Code hotspots fetch failed: ${res.status}`);
    return await res.json();
  }

  /**
   * 3. AI Model Committee: Retrieves active committee member personas.
   */
  async getCommitteeMembers() {
    const res = await fetch(`${this.config.baseUrl}/committee/members`, {
      headers: this.headers,
    });
    if (!res.ok) throw new Error(`Committee members fetch failed: ${res.status}`);
    return await res.json();
  }

  /**
   * 3. AI Model Committee: Convenes multi-agent debate and consensus vote on a patch/defect.
   */
  async runCommitteeReview(projectId, bugId, filePath, patchDiff = null, defectDescription = null) {
    const res = await fetch(`${this.config.baseUrl}/projects/${encodeURIComponent(projectId)}/committee/review`, {
      method: 'POST',
      headers: this.headers,
      body: JSON.stringify({
        bug_id: bugId,
        file_path: filePath,
        patch_diff: patchDiff,
        defect_description: defectDescription,
      }),
    });
    if (!res.ok) throw new Error(`Committee deliberation failed: ${res.status}`);
    return await res.json();
  }

  /**
   * 4. Long-Term Learning: Fetches learned repair patterns and statistics.
   */
  async getRepairMemory() {
    const res = await fetch(`${this.config.baseUrl}/observability/repair-memory`, {
      headers: this.headers,
    });
    if (!res.ok) throw new Error(`Repair memory fetch failed: ${res.status}`);
    return await res.json();
  }

  /**
   * 4. Long-Term Learning: Retrieves similar past repairs matching this defect.
   */
  async getSimilarRepairs(projectId, bugId) {
    const res = await fetch(`${this.config.baseUrl}/projects/${encodeURIComponent(projectId)}/bugs/${encodeURIComponent(bugId)}/similar-repairs`, {
      headers: this.headers,
    });
    if (!res.ok) return [];
    return await res.json();
  }

  /**
   * 5. API Security Testing: Audits REST endpoints against OWASP API Top 10.
   */
  async auditApiSecurity(projectId) {
    const res = await fetch(`${this.config.baseUrl}/projects/${encodeURIComponent(projectId)}/api-security/audit`, {
      headers: this.headers,
    });
    if (!res.ok) throw new Error(`API Security audit failed: ${res.status}`);
    return await res.json();
  }

  /**
   * 6. Bug Origin Detection: Traces introducing commit, author, PR, and flaw age.
   */
  async getBugOrigin(projectId, bugId, filePath = null, lineNumber = null) {
    const params = new URLSearchParams();
    if (filePath) params.set('file_path', filePath);
    if (lineNumber) params.set('line_number', lineNumber.toString());
    const queryStr = params.toString() ? `?${params.toString()}` : '';
    const res = await fetch(`${this.config.baseUrl}/projects/${encodeURIComponent(projectId)}/bugs/${encodeURIComponent(bugId)}/origin${queryStr}`, {
      headers: this.headers,
    });
    if (!res.ok) return null;
    return await res.json();
  }

  /**
   * 7. Automatic Documentation: Generates Architecture Decision Record (ADR).
   */
  async getAdrDocument(projectId, bugId = null) {
    const query = bugId ? `?bug_id=${encodeURIComponent(bugId)}` : '';
    const res = await fetch(`${this.config.baseUrl}/projects/${encodeURIComponent(projectId)}/documentation/adr${query}`, {
      headers: this.headers,
    });
    if (!res.ok) throw new Error(`ADR generation failed: ${res.status}`);
    return await res.json();
  }

  /**
   * 7. Automatic Documentation: Generates Security Remediation Changelog.
   */
  async getSecurityChangelog(projectId) {
    const res = await fetch(`${this.config.baseUrl}/projects/${encodeURIComponent(projectId)}/documentation/changelog`, {
      headers: this.headers,
    });
    if (!res.ok) throw new Error(`Security changelog generation failed: ${res.status}`);
    return await res.json();
  }

  /**
   * 7. Automatic Documentation: Generates Executive Remediation Brief.
   */
  async getExecutiveBrief(projectId) {
    const res = await fetch(`${this.config.baseUrl}/projects/${encodeURIComponent(projectId)}/documentation/executive-brief`, {
      headers: this.headers,
    });
    if (!res.ok) throw new Error(`Executive brief generation failed: ${res.status}`);
    return await res.json();
  }

  /**
   * Codebase Digital Twin: Topological dependency model.
   */
  async getDigitalTwin(projectId) {
    const res = await fetch(`${this.config.baseUrl}/projects/${encodeURIComponent(projectId)}/digital-twin`, {
      headers: this.headers,
    });
    if (!res.ok) throw new Error(`Digital Twin query failed: ${res.status}`);
    return await res.json();
  }

  /**
   * Codebase Digital Twin: Analyze patch blast radius & downstream impact for a bug.
   */
  async getBugDigitalTwinImpact(projectId, bugId, targetFile = null, lineNumber = null, functionHint = null) {
    const params = new URLSearchParams();
    if (targetFile) params.set('target_file', targetFile);
    if (lineNumber) params.set('line_number', lineNumber.toString());
    if (functionHint) params.set('function_hint', functionHint);

    let url = `${this.config.baseUrl}/projects/${encodeURIComponent(projectId)}/bugs/${encodeURIComponent(bugId)}/digital-twin-impact`;
    if (params.toString()) url += `?${params.toString()}`;

    const res = await fetch(url, {
      headers: this.headers,
    });
    if (!res.ok) throw new Error(`Digital Twin blast radius query failed: ${res.status}`);
    return await res.json();
  }

  /**
   * Codebase Digital Twin: Analyze patch blast radius for any target file or function in the project.
   */
  async analyzeDigitalTwinImpact(projectId, targetFile, lineNumber = null, functionHint = null, bugId = null) {
    const params = new URLSearchParams();
    if (targetFile) params.set('target_file', targetFile);
    if (lineNumber) params.set('line_number', lineNumber.toString());
    if (functionHint) params.set('function_hint', functionHint);
    if (bugId) params.set('bug_id', bugId);

    const res = await fetch(`${this.config.baseUrl}/projects/${encodeURIComponent(projectId)}/digital-twin/impact?${params.toString()}`, {
      headers: this.headers,
    });
    if (!res.ok) throw new Error(`Digital Twin blast radius query failed: ${res.status}`);
    return await res.json();
  }
}

// Global singleton instance
window.autopatch = new AutoPatchClient();
