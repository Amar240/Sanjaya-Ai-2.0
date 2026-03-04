"use client";

import { copy } from "@/lib/copy";
import type { PlanResponse } from "@/lib/types";

type PlanSummaryBarProps = {
  plan: PlanResponse;
  onViewReality: () => void;
  onFixGaps: () => void;
  onGenerateStoryboard: () => void;
  onAskAdvisor: () => void;
  storyboardLoading?: boolean;
};

function coveragePct(plan: PlanResponse): number {
  if (!plan.skill_coverage.length) {
    return 0;
  }
  const covered = plan.skill_coverage.filter((item) => item.covered).length;
  return Math.round((covered / plan.skill_coverage.length) * 100);
}

function warningCount(plan: PlanResponse): number {
  return plan.validation_errors.filter((item) => {
    const severity = String(item.details?.severity ?? "").toLowerCase();
    return severity !== "error";
  }).length;
}

export default function PlanSummaryBar({
  plan,
  onViewReality,
  onFixGaps,
  onGenerateStoryboard,
  onAskAdvisor,
  storyboardLoading = false,
}: PlanSummaryBarProps): JSX.Element {
  const hasReality = Boolean(plan.role_reality);
  const missingGaps = plan.gap_report?.missing_skills.length ?? 0;
  const readinessBand = plan.readiness_summary?.readiness_band ?? "Developing";
  const readinessScore = plan.readiness_summary?.score ?? 0;

  const coverage = coveragePct(plan);
  const warnings = warningCount(plan);

  const readinessPct = Math.round(readinessScore * 100);

  return (
    <article className="plan-summary-bar" id="plan-summary">
      <div className="summary-stats">
        <p>
          <strong>{plan.selected_role_title}</strong>
        </p>
        <div className="progress-mini" aria-label={`Skills covered ${coverage}%`}>
          <span className="muted summary-stats__line" style={{ minWidth: "4.5em" }}>
            Skills: <strong style={{ color: "var(--color-achievement)" }}>{coverage}%</strong>
          </span>
          <div className="progress-mini__bar" role="progressbar" aria-valuenow={coverage} aria-valuemin={0} aria-valuemax={100}>
            <div className="progress-mini__fill progress-mini__fill--primary" style={{ width: `${coverage}%` }} />
          </div>
        </div>
        <div className="progress-mini" aria-label={`Readiness ${readinessPct}%`}>
          <span className="muted summary-stats__line" style={{ minWidth: "4.5em" }}>
            Readiness: <strong>{readinessBand}</strong> ({readinessPct}%)
          </span>
          <div className="progress-mini__bar" role="progressbar" aria-valuenow={readinessPct} aria-valuemin={0} aria-valuemax={100}>
            <div className="progress-mini__fill" style={{ width: `${readinessPct}%` }} />
          </div>
        </div>
        <p className="muted summary-stats__line">
          <strong>{warnings}</strong> items to review · <strong>{missingGaps}</strong> gaps · Reality: <strong>{hasReality ? "Available" : "Partial"}</strong>
        </p>
      </div>
      <p className="muted">
        {copy.summaryBar.disclaimer}
      </p>
    </article>
  );
}
