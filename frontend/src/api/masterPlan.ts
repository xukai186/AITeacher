import { api } from "./client";

export type MasterPlanVersion = {
  id: string;
  version: number;
  source: string;
  weekly_goals_json: unknown[] | null;
  daily_time_budget_json: { date: string; minutes: number }[] | null;
  created_at: string;
};

export type MasterPlanState = {
  plan_id: string | null;
  plan_status: string | null;
  active_version: MasterPlanVersion | null;
  pending_version: MasterPlanVersion | null;
  budget_change_ratio: number | null;
  requires_confirmation: boolean;
};

export function fetchMasterPlan() {
  return api<MasterPlanState>("/student/master-plan");
}

export function confirmMasterPlan() {
  return api<{ active_version: MasterPlanVersion; message: string }>(
    "/student/master-plan/confirm",
    { method: "POST" },
  );
}

export function rejectMasterPlan() {
  return api<void>("/student/master-plan/reject", { method: "POST" });
}
