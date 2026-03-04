"use client";

import { useEffect, useRef, useState } from "react";

import { askAdvisor } from "@/lib/api";
import { copy } from "@/lib/copy";
import type { AdvisorCitation, AdvisorResponse, PlanResponse } from "@/lib/types";

type AdvisorQAPanelProps = {
  plan: PlanResponse;
  queuedQuestion?: string | null;
  queuedQuestionNonce?: number;
  focusNonce?: number;
};

function anchorId(prefix: string, raw: string): string {
  return `${prefix}-${raw.replace(/[^a-zA-Z0-9_-]/g, "-")}`;
}

function scrollToCitationTarget(citation: AdvisorCitation): void {
  const targetId = citation.evidence_id
    ? anchorId("evidence", citation.evidence_id)
    : citation.course_id
      ? anchorId("course", citation.course_id)
      : citation.skill_id
        ? anchorId("skill", citation.skill_id)
        : "";
  if (!targetId) {
    return;
  }
  const node = document.getElementById(targetId);
  if (!node) {
    return;
  }
  node.scrollIntoView({ behavior: "smooth", block: "center" });
  node.classList.add("target-highlight");
  window.setTimeout(() => node.classList.remove("target-highlight"), 1200);
}

export default function AdvisorQAPanel({
  plan,
  queuedQuestion,
  queuedQuestionNonce,
  focusNonce,
}: AdvisorQAPanelProps): JSX.Element {
  const [question, setQuestion] = useState<string>(copy.advisor.chips[0]);
  const [tone, setTone] = useState<"friendly" | "concise">("friendly");
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string>("");
  const [result, setResult] = useState<AdvisorResponse | null>(null);
  const [lastAskedQuestion, setLastAskedQuestion] = useState<string | null>(null);
  const questionInputRef = useRef<HTMLInputElement | null>(null);

  async function handleAsk(explicitQuestion?: string): Promise<void> {
    const content = (explicitQuestion ?? question).trim();
    if (!content) {
      return;
    }
    setLoading(true);
    setError("");
    setLastAskedQuestion(content);
    try {
      const response = await askAdvisor({
        question: content,
        plan_id: plan.plan_id,
        tone,
      });
      setResult(response);
    } catch (e) {
      setError(e instanceof Error ? e.message : copy.errors.advisorFailed);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!queuedQuestion || !queuedQuestionNonce) {
      return;
    }
    setQuestion(queuedQuestion);
    void handleAsk(queuedQuestion);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [queuedQuestionNonce]);

  useEffect(() => {
    if (!focusNonce) {
      return;
    }
    questionInputRef.current?.focus();
  }, [focusNonce]);

  return (
    <article className="subpanel advisor-panel" id="advisor-panel">
      <h3>{copy.advisor.title}</h3>
      <p className="muted">{copy.advisor.helper}</p>

      <div className="chat-actions" style={{ marginBottom: "var(--space-2)" }}>
        {copy.advisor.chips.map((chipText) => (
          <button
            key={chipText}
            type="button"
            className={`ui-chip ${lastAskedQuestion === chipText && result ? "ui-chip--selected" : ""}`}
            onClick={() => { setQuestion(chipText); void handleAsk(chipText); }}
            disabled={loading}
            style={{ cursor: "pointer" }}
            aria-pressed={lastAskedQuestion === chipText && !!result}
          >
            {chipText}
          </button>
        ))}
      </div>

      <div className="advisor-inputs">
        <input
          ref={questionInputRef}
          type="text"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder={copy.advisor.placeholder}
          disabled={loading}
        />
        <select
          value={tone}
          onChange={(event) => setTone(event.target.value as "friendly" | "concise")}
          disabled={loading}
        >
          <option value="friendly">Friendly</option>
          <option value="concise">Concise</option>
        </select>
        <button
          type="button"
          className="btn-primary"
          onClick={() => void handleAsk()}
          disabled={loading || !question.trim()}
        >
          {loading ? copy.advisor.askLoading : copy.advisor.askButton}
        </button>
      </div>

      {error ? <p className="error-line">{error}</p> : null}

      {result ? (
        <div className="advisor-result">
          <p>
            <strong>Answer:</strong> {result.answer}
          </p>
          <details className="advisor-meta-details">
            <summary>How we answered</summary>
            <div style={{ marginTop: "var(--space-2)" }}>
              <p className="muted">
                Plan: <span className="mono">{result.plan_id}</span> · Intent: {result.intent} · Confidence: {Math.round(result.confidence * 100)}% · LLM: {result.llm_status}
              </p>
              {result.llm_status === "fallback" ? (
                <p className="muted">
                  Fallback means deterministic advisor logic answered because the live LLM call was unavailable.
                </p>
              ) : null}
              {result.llm_error ? (
                <p className="muted">LLM detail: {result.llm_error}</p>
              ) : null}
            </div>
          </details>

          {result.reasoning_points.length ? (
            <>
              <h4>Reasoning</h4>
              <ul className="plain-list">
                {result.reasoning_points.map((item, idx) => (
                  <li key={`${item}-${idx}`}>{item}</li>
                ))}
              </ul>
            </>
          ) : null}

          {result.citations.length ? (
            <>
              <h4>Citations</h4>
              <ul className="plain-list">
                {result.citations.map((item, idx) => (
                  <li key={`${item.label}-${idx}`}>
                    <p>
                      <strong>{item.label}</strong> ({item.citation_type})
                    </p>
                    <p className="muted">{item.detail}</p>
                    {item.source_url ? (
                      <a href={item.source_url} target="_blank" rel="noreferrer">
                        Open source
                      </a>
                    ) : null}
                    {item.evidence_id || item.course_id || item.skill_id ? (
                      <button
                        type="button"
                        className="btn-secondary"
                        onClick={() => scrollToCitationTarget(item)}
                      >
                        Jump to context
                      </button>
                    ) : null}
                  </li>
                ))}
              </ul>
            </>
          ) : null}
        </div>
      ) : null}
    </article>
  );
}
