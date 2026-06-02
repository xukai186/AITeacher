import { api } from "./client";

export type ModelPolicy = {
  id: string;
  org_id: string;
  scene: string;
  provider: string;
  model: string;
  params: Record<string, unknown>;
};

export type ModelPolicyUpsert = {
  scene: string;
  provider: string;
  model: string;
  params: Record<string, unknown>;
};

export function listModelPolicies() {
  return api<ModelPolicy[]>("/admin/model-policies");
}

export function upsertModelPolicy(scene: string, body: ModelPolicyUpsert) {
  return api<ModelPolicy>(`/admin/model-policies/${encodeURIComponent(scene)}`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}
