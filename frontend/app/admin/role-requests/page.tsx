"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { fetchRoleRequests } from "@/lib/api";
import type { RoleRequestItem } from "@/lib/types";

export default function RoleRequestsPage(): JSX.Element {
  const [items, setItems] = useState<RoleRequestItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string>("");

  useEffect(() => {
    let cancelled = false;
    fetchRoleRequests({ status: "open", show_all: true })
      .then((rows) => {
        if (!cancelled) setItems(rows);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load role requests");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main className="panel admin-page">
      <div className="panel-header">
        <h1>Role Requests Inbox</h1>
        <p>Aggregated unknown role queries from student intake.</p>
      </div>
      <div className="admin-nav">
        <Link href="/admin/insights">Back to Insights</Link>
      </div>
      {loading ? <p>Loading role requests...</p> : null}
      {error ? <p className="error-line">{error}</p> : null}
      {!loading && !error ? (
        <table className="admin-table">
          <thead>
            <tr>
              <th>Role Query</th>
              <th>Count</th>
              <th>Last Seen</th>
              <th>Top Candidate</th>
              <th>Status</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.role_request_id}>
                <td>{item.role_query_norm}</td>
                <td>{item.count}</td>
                <td>{item.last_seen}</td>
                <td>{item.top_candidates[0]?.role_id ?? "-"}</td>
                <td>{item.status}</td>
                <td>
                  <Link href={`/admin/role-requests/${item.role_request_id}`}>Open</Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
    </main>
  );
}
