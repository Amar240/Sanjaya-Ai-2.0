"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { askAdvisor } from "@/lib/api";
import { copy } from "@/lib/copy";
import type { AdvisorCitation, AdvisorResponse } from "@/lib/types";
import { Button } from "@/components/ui";

type CatalogCourse = {
  course_id: string;
  title: string;
  description: string;
  source_url: string;
};

type CourseQADialogProps = {
  courseId: string;
  courseTitle: string;
  planId: string;
  onClose: () => void;
};

function scrollToCitationTarget(citation: AdvisorCitation): void {
  const prefix = "course";
  const raw = citation.evidence_id ?? citation.course_id ?? citation.skill_id ?? "";
  const targetId = raw ? `${prefix}-${String(raw).replace(/[^a-zA-Z0-9_-]/g, "-")}` : "";
  if (!targetId) return;
  const node = document.getElementById(targetId);
  if (!node) return;
  node.scrollIntoView({ behavior: "smooth", block: "center" });
  node.classList.add("target-highlight");
  window.setTimeout(() => node.classList.remove("target-highlight"), 1200);
}

export default function CourseQADialog({
  courseId,
  courseTitle,
  planId,
  onClose,
}: CourseQADialogProps): JSX.Element {
  const [course, setCourse] = useState<CatalogCourse | null>(null);
  const [courseLoading, setCourseLoading] = useState(true);
  const [courseError, setCourseError] = useState(false);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<AdvisorResponse | null>(null);
  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    setCourseLoading(true);
    setCourseError(false);
    fetch(`/api/catalog/course/${encodeURIComponent(courseId)}`)
      .then((res) => {
        if (!res.ok) throw new Error("Course not found");
        return res.json();
      })
      .then((data: CatalogCourse) => {
        if (!cancelled) setCourse(data);
      })
      .catch(() => {
        if (!cancelled) setCourseError(true);
      })
      .finally(() => {
        if (!cancelled) setCourseLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [courseId]);

  const handleAsk = useCallback(
    async (explicitQuestion?: string) => {
      const content = (explicitQuestion ?? question).trim();
      if (!content) return;
      setLoading(true);
      setError("");
      setResult(null);
      try {
        const response = await askAdvisor({
          question: content,
          plan_id: planId,
          course_id: courseId,
          tone: "friendly",
        });
        setResult(response);
      } catch (e) {
        setError(e instanceof Error ? e.message : copy.errors.advisorFailed);
      } finally {
        setLoading(false);
      }
    },
    [courseId, planId, question]
  );

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  useEffect(() => {
    dialogRef.current?.focus();
  }, []);

  const title = course?.title ?? courseTitle;
  const description = course?.description ?? "";
  const sourceUrl = course?.source_url ?? "";

  return (
    <div
      className="course-qa-dialog-overlay"
      role="dialog"
      aria-labelledby="course-qa-dialog-title"
      aria-modal="true"
      ref={dialogRef}
      tabIndex={-1}
    >
      <div className="course-qa-dialog">
        <div className="course-qa-dialog__header">
          <h2 id="course-qa-dialog-title" className="course-qa-dialog__title">
            {courseId} — {title}
          </h2>
          <button
            type="button"
            className="ui-btn ui-btn--ghost"
            onClick={onClose}
            aria-label="Close dialog"
          >
            Close
          </button>
        </div>

        <div className="course-qa-dialog__body">
          {courseLoading ? (
            <p className="muted">Loading course details…</p>
          ) : courseError ? (
            <p className="muted">{copy.courseQA.noDescription}</p>
          ) : (
            <>
              {description ? (
                <div className="course-qa-dialog__description">
                  <p>{description}</p>
                  {sourceUrl ? (
                    <a
                      href={sourceUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="course-qa-dialog__link"
                    >
                      View in catalog
                    </a>
                  ) : null}
                </div>
              ) : null}
            </>
          )}

          <div className="course-qa-dialog__qa">
            <h3>{copy.courseQA.title}</h3>
            <div className="chat-actions" style={{ marginBottom: "var(--space-2)" }}>
              {copy.courseQA.chips.map((chipText) => (
                <button
                  key={chipText}
                  type="button"
                  className="ui-chip"
                  onClick={() => void handleAsk(chipText)}
                  disabled={loading}
                  style={{ cursor: "pointer" }}
                >
                  {chipText}
                </button>
              ))}
            </div>
            <div className="advisor-inputs">
              <input
                type="text"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder={copy.courseQA.placeholder}
                disabled={loading}
                onKeyDown={(e) => {
                  if (e.key === "Enter") void handleAsk();
                }}
              />
              <Button
                onClick={() => void handleAsk()}
                disabled={loading || !question.trim()}
              >
                {loading ? copy.courseQA.askLoading : copy.courseQA.askButton}
              </Button>
            </div>
          </div>

          {error ? <p className="error-line">{error}</p> : null}

          {result ? (
            <div className="advisor-result course-qa-dialog__result">
              <p>
                <strong>Answer:</strong> {result.answer}
              </p>
              <p className="muted">
                Intent: {result.intent} | Confidence:{" "}
                {Math.round(result.confidence * 100)}%
              </p>
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
                          <a
                            href={item.source_url}
                            target="_blank"
                            rel="noreferrer"
                          >
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
        </div>
      </div>
    </div>
  );
}
