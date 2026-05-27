import { api } from "./client";

export type Package = { id: string; name: string; subject_codes: string[] };

export function listPackages() {
  return api<Package[]>("/admin/packages");
}

export function createPackage(body: { name: string; subject_codes: string[] }) {
  return api<Package>("/admin/packages", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function assignPackage(studentId: string, packageId: string) {
  return api<{ subject_codes: string[] }>(`/admin/students/${studentId}/package`, {
    method: "POST",
    body: JSON.stringify({ package_id: packageId }),
  });
}
