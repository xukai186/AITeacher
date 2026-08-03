import { api } from "./client";

export type DailyTaskPayload = {
  source?: string;
  syllabus_node_id?: string;
  [key: string]: unknown;
};

export type DailyTaskOut = {
  id: string;
  date: string;
  subject_code: string;
  type: string;
  ref_id: string | null;
  status: string;
  est_minutes: number;
  title: string;
  created_at: string;
  payload_json?: DailyTaskPayload | null;
};

export type TodayTasksOut = {
  date: string;
  tasks: DailyTaskOut[];
};

export function fetchTodayTasks() {
  return api<TodayTasksOut>("/student/tasks/today");
}

