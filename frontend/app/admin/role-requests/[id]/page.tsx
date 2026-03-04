"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import {
  createRoleFromRequest,
  fetchRoleRequestById,
  fetchRoles,
  ignoreRoleRequest,
  mapRoleRequest
} from "@/lib/api";
import type { RoleOption, RoleRequestItem } from "@/lib/types";

type Params = { params: { id: string } };

export default function RoleRequestDetailPage({ params }: Params): JSX.Element {
  const [item, setItem] = useState<RoleRequestItem | null>(null);
  const [roles, setRoles] = useState<RoleOption[]>([]);
  const [selectedRoleId, setSelectedRoleId] = useState<string>("");
  const [note, setNote] = useState<string>("");
  const [error, setError] = useState<string>("");
  const [busy, setBusy] = useState<boolean>(false);
  const router = useRouter();

  useEffect(() => {
    let cancelled = false;
    Promise.all([fetchRoleRequestById(params.id), fetchRoles()])
      .then(([requestItem, roleList]) => {
        if (cancelled) return;
        setItem(requestItem);
        setRoles(roleList);
        setSelectedRoleId(roleList[0]?.role_id ?? "");
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load request");
      });
    return () => {
      cancelled = true;
    };
  }, [params.id]);

  async function handleIgnore(): Promise<void> {
    setBusy(true);
    setError("");
    try {
      const updated = await ignoreRoleRequest(params.id);
      setItem(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to ignore request");
    } finally {
      setBusy(false);
    }
  }

  async function handleMap(): Promise<void> {
    if (!selectedRoleId) return;
    setBusy(true);
    setError("");
    try {
      const updated = await mapRoleRequest(params.id, selectedRoleId, note);
      setItem(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to map role request");
    } finally {
      setBusy(false);
    }
  }

  async function handleCreateRole(): Promise<void> {
    setBusy(true);
    setError("");
    try {
      const payload = await createRoleFromRequest(params.id);
      router.push(`/admin/drafts/${payload.draft_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create role draft");
      setBusy(false);
    }
  }

  return (
    <main className="panel admin-page">
      <div className="panel-header">
        <h1>Role Request Detail</h1>
        <p>Map this request to an existing curated role or create a new draft role.</p>
      </div>
      <div className="admin-nav">
        <Link href="/admin/role-requests">Back to Inbox</Link>
      </div>
      {error ? <p className="error-line">{error}</p> : null}
      {item ? (
        <section className="grid-two">
          <article className="panel">
            <h3>Request</h3>
            <p>
              <strong>Normalized:</strong> {item.role_query_norm}
            </p>
            <p>
              <strong>Count:</strong> {item.count}
            </p>
            <p>
              <strong>Status:</strong> {item.status}
            </p>
            <p>
              <strong>Examples:</strong> {item.examples.join(" | ")}
            </p>
          </article>
          <article className="panel">
            <h3>Top Candidates</h3>
            <ul>
              {item.top_candidates.map((candidate) => (
                <li key={candidate.role_id}>
                  {candidate.role_id} ({candidate.score.toFixed(3)})
                </li>
              ))}
            </ul>
          </article>
          <article className="panel">
            <h3>Map to Existing Role</h3>
            <select
              value={selectedRoleId}
              onChange={(event) => setSelectedRoleId(event.target.value)}
            >
              {roles.map((role) => (
                <option key={role.role_id} value={role.role_id}>
                  {role.title} ({role.role_id})
                </option>
              ))}
            </select>
            <input
              type="text"
              value={note}
              onChange={(event) => setNote(event.target.value)}
              placeholder="Optional note"
            />
            <button type="button" className="btn-primary" onClick={handleMap} disabled={busy}>
              Map Request
            </button>
          </article>
          <article className="panel">
            <h3>Create New Role Draft</h3>
            <button type="button" className="btn-primary" onClick={handleCreateRole} disabled={busy}>
              Create Role
            </button>
            <button type="button" className="btn-muted" onClick={handleIgnore} disabled={busy}>
              Ignore Request
            </button>
          </article>
        </section>
      ) : (
        <p>Loading...</p>
      )}
    </main>
  );
}
