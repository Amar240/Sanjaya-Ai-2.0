"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { fetchAdminInsights } from "@/lib/api";
import type { InsightsSummary } from "@/lib/types";

export default function AdminInsightsPage(): JSX.Element {
  const [window, setWindow] = useState<"7d" | "30d">("30d");
  const [data, setData] = useState<InsightsSummary | null>(null);
  const [error, setError] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    fetchAdminInsights(window)
      .then((payload) => {
        if (!cancelled) {
          setData(payload);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load insights");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [window]);

  return (
    <main className="panel admin-page">
      <div className="panel-header">
        <h1>Advisor Insights</h1>
        <p>Usage and integrity trends from privacy-safe analytics events.</p>
      </div>
      <div className="admin-nav">
        <Link href="/admin/role-requests">Role Requests Inbox</Link>
      </div>
      <div className="button-group">
        <button
          type="button"
          className={window === "7d" ? "btn-primary" : "btn-muted"}
          onClick={() => setWindow("7d")}
        >
          Last 7d
        </button>
        <button
          type="button"
          className={window === "30d" ? "btn-primary" : "btn-muted"}
          onClick={() => setWindow("30d")}
        >
          Last 30d
        </button>
      </div>
      {loading ? <p>Loading insights...</p> : null}
      {error ? <p className="error-line">{error}</p> : null}
      {data ? (
        <section className="grid-two">
          <article className="panel">
            <h3>Top Roles Selected</h3>
            <ul>
              {data.top_roles_selected.map((item) => (
                <li key={item.key}>
                  {item.key}: {item.count}
                </li>
              ))}
            </ul>
          </article>
          <article className="panel">
            <h3>Top Error Codes</h3>
            <ul>
              {data.top_error_codes.map((item) => (
                <li key={item.key}>
                  {item.key}: {item.count}
                </li>
              ))}
            </ul>
          </article>
          <article className="panel">
            <h3>Top Intents</h3>
            <ul>
              {data.top_intents.map((item) => (
                <li key={item.key}>
                  {item.key}: {item.count}
                </li>
              ))}
            </ul>
          </article>
          <article className="panel">
            <h3>Top Role Searches</h3>
            <ul>
              {data.top_role_searches.map((item) => (
                <li key={item.key}>
                  {item.key}: {item.count}
                </li>
              ))}
            </ul>
          </article>
          <article className="panel">
            <h3>Unknown Role Requests</h3>
            <p>{data.top_unknown_role_requests.length} tracked requests</p>
            <ul>
              {data.top_unknown_role_requests.map((item) => (
                <li key={item.role_request_id}>
                  {item.role_query_norm}: {item.count}
                </li>
              ))}
            </ul>
          </article>
          <article className="panel">
            <h3>Severity Breakdown</h3>
            <p>Warnings: {data.severity_breakdown.warnings}</p>
            <p>Errors: {data.severity_breakdown.errors}</p>
          </article>
        </section>
      ) : null}
    </main>
  );
}
