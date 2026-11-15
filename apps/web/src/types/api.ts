/**
 * Strongly typed API contracts for AI Job Application Agent dashboard (Phase 2.4).
 *
 * AUTHORITY:
 * - docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Section 14)
 * - docs/BUILD_RULES.md
 */

export interface DashboardOverview {
  user_id: string;
  generated_at: string;
  jobs_discovered: number;
  jobs_matched: number;
  eligible_jobs: number;
  applications_awaiting_approval: number;
  applications_needing_input: number;
  dry_runs_completed: number;
  rejected_jobs: number;
  skipped_applications: number;
  failed_runs: number;
  kill_switch_active: boolean;
  real_submit_gate_locked: boolean;
  provider_health: Record<string, string>;
}

export interface FunnelAnalytics {
  discovered: number;
  matched: number;
  eligible: number;
  ready: number;
  awaiting_approval: number;
  approved_and_filling: number;
  dry_run_done: number;
  applied_live: number;
}

export interface ApplicationItem {
  id: string;
  job_id: string;
  user_id: string;
  platform: string;
  external_id: string;
  profile_version: string;
  resume_version?: string | null;
  autonomy_level: "L0" | "L1" | "L2" | "L3";
  status: string;
  fields_filled?: Record<string, string>;
  evidence_ref?: string | null;
  error?: string | null;
  applied_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface PaginatedApplications {
  items: ApplicationItem[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

export interface TimelineEvent {
  id: string;
  application_id: string;
  event_type: string;
  previous_status?: string | null;
  new_status?: string | null;
  reason?: string | null;
  triggering_component?: string | null;
  timestamp: string;
  payload: Record<string, unknown>;
}

export interface ProfileSyncResponse {
  status: string;
  profile_version: string;
  candidate_name: string;
  synced_at: string;
}

export interface APIError {
  error: string;
  detail: string;
  correlation_id?: string;
  timestamp: string;
  code?: string;
}
