"use client";

import { useState } from "react";

import type { EvidencePanelItem } from "@/lib/types";

type EvidenceRefProps = {
  evidence: EvidencePanelItem;
  compact?: boolean;
};

export default function EvidenceRef({
  evidence,
  compact = false,
}: EvidenceRefProps): JSX.Element {
  const [copied, setCopied] = useState<boolean>(false);

  async function handleCopyId(): Promise<void> {
    try {
      await navigator.clipboard.writeText(evidence.evidence_id);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 900);
    } catch {
      setCopied(false);
    }
  }

  return (
    <div
      className={`evidence-ref ${compact ? "compact" : ""}`}
      title={`Evidence ID: ${evidence.evidence_id}`}
    >
      <div className="evidence-ref-head">
        <p>
          <strong>{evidence.source_provider}</strong>
        </p>
        <p className="muted">{evidence.source_title}</p>
        <p className="muted evidence-ref-meta">
          {evidence.retrieval_method}
          {typeof evidence.rank_score === "number"
            ? ` • rank ${evidence.rank_score.toFixed(3)}`
            : ""}
        </p>
      </div>
      <div className="evidence-ref-actions">
        <a
          href={evidence.source_url}
          target="_blank"
          rel="noreferrer"
          className="btn-muted evidence-link-btn"
        >
          Open Source
        </a>
        <button type="button" className="btn-muted" onClick={() => void handleCopyId()}>
          {copied ? "Copied" : "Copy ID"}
        </button>
      </div>
    </div>
  );
}
