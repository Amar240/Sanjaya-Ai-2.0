"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

type Params = { params: { draftId: string } };

type DraftRole = {
  role_id: string;
  title: string;
  summary: string;
  market_grounding: "direct" | "composite";
  required_skills: { skill_id: string; importance: number }[];
  evidence_sources: string[];
  created_by?: string;
  created_at?: string;
  role_origin?: string;
  department_owner?: string;
  country_scope?: string;
  demo_tier?: "core" | "fusion" | "extended";
  reality_complete?: boolean;
  project_coverage_complete?: boolean;
};

type ReadinessRow = {
  role_id: string;
  department_owner: string;
  demo_tier: string;
  gate1_required_skills_evidence_ok: boolean;
  gate2_role_reality_ok: boolean;
  gate3_project_coverage_ok: boolean;
  missing_project_skills: string[];
};

export default function DraftRolesPage({ params }: Params): JSX.Element {
  const [items, setItems] = useState<DraftRole[]>([]);
  const [error, setError] = useState<string>("");
  const [busy, setBusy] = useState<boolean>(false);
  const [roleId, setRoleId] = useState<string>("");
  const [title, setTitle] = useState<string>("");
  const [summary, setSummary] = useState<string>("");
  const [marketGrounding, setMarketGrounding] = useState<"direct" | "composite">("direct");
  const [departmentOwner, setDepartmentOwner] = useState<string>("CIS");
  const [demoTier, setDemoTier] = useState<"core" | "fusion" | "extended">("extended");
  const [readinessRows, setReadinessRows] = useState<ReadinessRow[]>([]);
  const [filterDept, setFilterDept] = useState<string>("");

  const canCreate = useMemo(() => roleId.trim() && title.trim(), [roleId, title]);

  async function loadRoles(): Promise<void> {
    setError("");
    const qs = new URLSearchParams();
    if (filterDept.trim()) qs.set("department_owner", filterDept.trim().toUpperCase());
    const res = await fetch(`/api/admin/drafts/${encodeURIComponent(params.draftId)}/roles?${qs.toString()}`, {
      method: "GET",
      cache: "no-store"
    });
    const payload = await res.json().catch(() => null);
    if (!res.ok) {
      throw new Error(
        payload && typeof payload === "object" && "detail" in payload
          ? String((payload as { detail: unknown }).detail)
          : "Failed to load draft roles"
      );
    }
    const data = payload as { items?: DraftRole[] };
    setItems(data.items ?? []);

    const readinessRes = await fetch(
      `/api/admin/drafts/${encodeURIComponent(params.draftId)}/roles/readiness?${qs.toString()}`,
      { method: "GET", cache: "no-store" }
    );
    const readinessPayload = await readinessRes.json().catch(() => null);
    if (!readinessRes.ok) {
      throw new Error(
        readinessPayload && typeof readinessPayload === "object" && "detail" in readinessPayload
          ? String((readinessPayload as { detail: unknown }).detail)
          : "Failed to load readiness status"
      );
    }
    const readinessData = readinessPayload as { items?: ReadinessRow[] };
    setReadinessRows(readinessData.items ?? []);
  }

  useEffect(() => {
    loadRoles().catch((err: unknown) => {
      setError(err instanceof Error ? err.message : "Failed to load draft");
    });
  }, [params.draftId, filterDept]);

  async function createRole(): Promise<void> {
    if (!canCreate) return;
    setBusy(true);
    setError("");
    try {
      const res = await fetch(`/api/admin/drafts/${encodeURIComponent(params.draftId)}/roles`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          role_id: roleId.trim().toUpperCase(),
          title: title.trim(),
          summary: summary.trim(),
          market_grounding: marketGrounding,
          required_skills: [],
          evidence_sources: [],
          department_owner: departmentOwner.trim().toUpperCase() || "EXTENDED",
          country_scope: "USA",
          demo_tier: demoTier
        })
      });
      const payload = await res.json().catch(() => null);
      if (!res.ok) {
        throw new Error(
          payload && typeof payload === "object" && "detail" in payload
            ? String((payload as { detail: unknown }).detail)
            : "Failed to create role"
        );
      }
      setRoleId("");
      setTitle("");
      setSummary("");
      await loadRoles();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create role");
    } finally {
      setBusy(false);
    }
  }

  async function deleteRole(targetRoleId: string): Promise<void> {
    setBusy(true);
    setError("");
    try {
      const res = await fetch(
        `/api/admin/drafts/${encodeURIComponent(params.draftId)}/roles/${encodeURIComponent(targetRoleId)}`,
        { method: "DELETE" }
      );
      const payload = await res.json().catch(() => null);
      if (!res.ok) {
        throw new Error(
          payload && typeof payload === "object" && "detail" in payload
            ? String((payload as { detail: unknown }).detail)
            : "Failed to delete role"
        );
      }
      await loadRoles();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete role");
    } finally {
      setBusy(false);
    }
  }

  async function publishDraft(): Promise<void> {
    setBusy(true);
    setError("");
    try {
      const res = await fetch(`/api/admin/drafts/${encodeURIComponent(params.draftId)}/publish`, {
        method: "POST"
      });
      const payload = await res.json().catch(() => null);
      if (!res.ok) {
        throw new Error(
          payload && typeof payload === "object" && "detail" in payload
            ? String((payload as { detail: unknown }).detail)
            : "Failed to publish draft"
        );
      }
      await loadRoles();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to publish draft");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="panel admin-page">
      <div className="panel-header">
        <h1>Draft Roles Editor</h1>
        <p>Draft ID: {params.draftId}</p>
      </div>
      <div className="admin-nav">
        <Link href="/admin/role-requests">Back to Role Requests</Link>
      </div>
      {error ? <p className="error-line">{error}</p> : null}
      <section className="panel">
        <h3>Create Role</h3>
        <div className="field-grid">
          <input
            type="text"
            value={roleId}
            placeholder="ROLE_NEW_ID"
            onChange={(event) => setRoleId(event.target.value)}
          />
          <input
            type="text"
            value={title}
            placeholder="Role title"
            onChange={(event) => setTitle(event.target.value)}
          />
          <select
            value={marketGrounding}
            onChange={(event) => setMarketGrounding(event.target.value as "direct" | "composite")}
          >
            <option value="direct">direct</option>
            <option value="composite">composite</option>
          </select>
          <input
            type="text"
            value={departmentOwner}
            placeholder="Department owner (e.g. CIS)"
            onChange={(event) => setDepartmentOwner(event.target.value)}
          />
          <select
            value={demoTier}
            onChange={(event) => setDemoTier(event.target.value as "core" | "fusion" | "extended")}
          >
            <option value="core">core</option>
            <option value="fusion">fusion</option>
            <option value="extended">extended</option>
          </select>
        </div>
        <textarea
          value={summary}
          placeholder="Role summary"
          onChange={(event) => setSummary(event.target.value)}
        />
        <div className="button-group">
          <button type="button" className="btn-primary" onClick={createRole} disabled={!canCreate || busy}>
            Add Role
          </button>
          <button type="button" className="btn-primary" onClick={publishDraft} disabled={busy}>
            Publish Draft
          </button>
        </div>
      </section>
      <section className="panel">
        <h3>Roles</h3>
        <div className="field-grid">
          <input
            type="text"
            value={filterDept}
            placeholder="Filter by department owner"
            onChange={(event) => setFilterDept(event.target.value)}
          />
        </div>
        <table className="admin-table">
          <thead>
            <tr>
              <th>Role ID</th>
              <th>Title</th>
              <th>Dept</th>
              <th>Tier</th>
              <th>Origin</th>
              <th>Created By</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.role_id}>
                <td>{item.role_id}</td>
                <td>{item.title}</td>
                <td>{item.department_owner ?? "-"}</td>
                <td>{item.demo_tier ?? "-"}</td>
                <td>{item.role_origin ?? "-"}</td>
                <td>{item.created_by ?? "-"}</td>
                <td>
                  <button
                    type="button"
                    className="btn-muted"
                    onClick={() => deleteRole(item.role_id)}
                    disabled={busy}
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      <section className="panel">
        <h3>Readiness Gates</h3>
        <table className="admin-table">
          <thead>
            <tr>
              <th>Role ID</th>
              <th>Tier</th>
              <th>Gate1</th>
              <th>Gate2</th>
              <th>Gate3</th>
              <th>Missing Project Skills</th>
            </tr>
          </thead>
          <tbody>
            {readinessRows.map((row) => (
              <tr key={`readiness-${row.role_id}`}>
                <td>{row.role_id}</td>
                <td>{row.demo_tier}</td>
                <td>{row.gate1_required_skills_evidence_ok ? "OK" : "BLOCK"}</td>
                <td>{row.gate2_role_reality_ok ? "OK" : "BLOCK"}</td>
                <td>{row.gate3_project_coverage_ok ? "OK" : "BLOCK"}</td>
                <td>{row.missing_project_skills.join(", ") || "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </main>
  );
}
