/**
 * Typed API Client for AI Job Application Agent (Phase 2.4).
 *
 * Implements standard headers, user JWT forwarding, and error envelope handling.
 */

import type {
  AnswerBankItem,
  ApplicationItem,
  CanaryRunResult,
  DashboardOverview,
  FunnelAnalytics,
  JobDetailItem,
  PaginatedApplications,
  PaginatedJobs,
  ProfileSyncResponse,
  ProviderStatusItem,
  ResumeItem,
  SessionStatusItem,
  TimelineEvent,
} from "../types/api";

export class APIClientError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public correlationId?: string
  ) {
    super(message);
    this.name = "APIClientError";
  }
}

export class JobAgentAPIClient {
  private baseUrl: string;
  private token?: string;

  constructor(baseUrl: string = "http://127.0.0.1:8000", token?: string) {
    this.baseUrl = baseUrl.replace(/\/$/, "");
    this.token = token;
  }

  public setToken(token: string): void {
    this.token = token;
  }

  private async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const url = `${this.baseUrl}${path}`;
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      Accept: "application/json",
      ...(options.headers as Record<string, string>),
    };

    if (this.token) {
      headers["Authorization"] = `Bearer ${this.token}`;
    }

    const response = await fetch(url, {
      ...options,
      headers,
    });

    if (!response.ok) {
      let errMessage = `HTTP Error ${response.status}`;
      let errCode = "api_error";
      let corrId: string | undefined = response.headers.get("X-Request-ID") ?? undefined;

      try {
        const body = await response.json();
        if (body.detail) errMessage = body.detail;
        if (body.error) errCode = body.error;
        if (body.correlation_id) corrId = body.correlation_id;
      } catch {
        // Fallback to text
      }

      throw new APIClientError(response.status, errCode, errMessage, corrId);
    }

    return response.json() as Promise<T>;
  }

  public async getOverview(): Promise<DashboardOverview> {
    return this.request<DashboardOverview>("/api/v1/dashboard/overview");
  }

  public async getApplications(params?: {
    status?: string;
    limit?: number;
    offset?: number;
  }): Promise<PaginatedApplications> {
    const query = new URLSearchParams();
    if (params?.status) query.set("status", params.status);
    if (params?.limit) query.set("limit", String(params.limit));
    if (params?.offset) query.set("offset", String(params.offset));
    const qs = query.toString() ? `?${query.toString()}` : "";
    return this.request<PaginatedApplications>(`/api/v1/dashboard/applications${qs}`);
  }

  public async getApprovals(): Promise<ApplicationItem[]> {
    return this.request<ApplicationItem[]>("/api/v1/dashboard/approvals");
  }

  public async approveApplication(id: string, notes?: string): Promise<{ status: string }> {
    return this.request<{ status: string }>(`/api/v1/applications/${id}/approve`, {
      method: "POST",
      body: JSON.stringify({ notes }),
    });
  }

  public async rejectApplication(id: string, reason?: string): Promise<{ status: string }> {
    return this.request<{ status: string }>(`/api/v1/applications/${id}/reject`, {
      method: "POST",
      body: JSON.stringify({ reason: reason || "User rejected" }),
    });
  }

  public async getApplicationDetail(id: string): Promise<ApplicationItem> {
    return this.request<ApplicationItem>(`/api/v1/dashboard/applications/${id}`);
  }

  public async getApplicationTimeline(id: string): Promise<TimelineEvent[]> {
    return this.request<TimelineEvent[]>(`/api/v1/dashboard/applications/${id}/timeline`);
  }

  public async getAnalytics(): Promise<FunnelAnalytics> {
    return this.request<FunnelAnalytics>("/api/v1/dashboard/analytics");
  }

  public async getJobs(params?: {
    search?: string;
    platform?: string;
    minScore?: number;
    workMode?: string;
    limit?: number;
    offset?: number;
  }): Promise<PaginatedJobs> {
    const query = new URLSearchParams();
    if (params?.search) query.set("search", params.search);
    if (params?.platform) query.set("platform", params.platform);
    if (params?.minScore) query.set("min_score", String(params.minScore));
    if (params?.workMode) query.set("work_mode", params.workMode);
    if (params?.limit) query.set("limit", String(params.limit));
    if (params?.offset) query.set("offset", String(params.offset));
    const qs = query.toString() ? `?${query.toString()}` : "";
    return this.request<PaginatedJobs>(`/api/v1/dashboard/jobs${qs}`);
  }

  public async getJobDetail(id: string): Promise<JobDetailItem> {
    return this.request<JobDetailItem>(`/api/v1/dashboard/jobs/${id}`);
  }

  public async syncProfile(): Promise<ProfileSyncResponse> {
    return this.request<ProfileSyncResponse>("/api/v1/dashboard/profile/sync", {
      method: "POST",
    });
  }

  public async getResumes(): Promise<ResumeItem[]> {
    return this.request<ResumeItem[]>("/api/v1/dashboard/resumes");
  }

  public async getAnswerBank(params?: {
    category?: string;
    search?: string;
  }): Promise<AnswerBankItem[]> {
    const query = new URLSearchParams();
    if (params?.category) query.set("category", params.category);
    if (params?.search) query.set("search", params.search);
    const qs = query.toString() ? `?${query.toString()}` : "";
    return this.request<AnswerBankItem[]>(`/api/v1/dashboard/answers${qs}`);
  }

  public async getProviderStatus(): Promise<ProviderStatusItem[]> {
    return this.request<ProviderStatusItem[]>("/api/v1/ops/providers");
  }

  public async runCanary(provider: string): Promise<CanaryRunResult> {
    return this.request<CanaryRunResult>(`/api/v1/ops/canaries/${provider}/run`, {
      method: "POST",
    });
  }

  public async getSessions(): Promise<SessionStatusItem[]> {
    return this.request<SessionStatusItem[]>("/api/v1/ops/sessions");
  }

  public async verifySession(platform: string): Promise<{ status: string }> {
    return this.request<{ status: string }>(`/api/v1/ops/sessions/${platform}/verify`, {
      method: "POST",
    });
  }

  public async clearSession(platform: string): Promise<{ status: string }> {
    return this.request<{ status: string }>(`/api/v1/ops/sessions/${platform}/clear`, {
      method: "POST",
    });
  }
}

export const apiClient = new JobAgentAPIClient();
