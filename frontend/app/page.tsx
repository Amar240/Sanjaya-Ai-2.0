"use client";

import { useEffect, useRef, useState } from "react";

import IntakeForm from "@/components/IntakeForm";
import PlanDashboard from "@/components/PlanDashboard";
import { Alert, Card, EmptyState } from "@/components/ui";
import { createPlan, fetchRoles } from "@/lib/api";
import { copy } from "@/lib/copy";
import type { PlanRequest, PlanResponse, RoleOption } from "@/lib/types";

export default function HomePage(): JSX.Element {
  const [roles, setRoles] = useState<RoleOption[]>([]);
  const [loadingRoles, setLoadingRoles] = useState<boolean>(true);
  const [planning, setPlanning] = useState<boolean>(false);
  const [pageError, setPageError] = useState<string>("");
  const [plan, setPlan] = useState<PlanResponse | null>(null);
  const planRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    let mounted = true;
    const loadRoles = async () => {
      setLoadingRoles(true);
      setPageError("");
      try {
        const data = await fetchRoles();
        if (mounted) {
          setRoles(data);
        }
      } catch (error) {
        if (mounted) {
          setPageError(
            error instanceof Error ? error.message : copy.errors.generic
          );
        }
      } finally {
        if (mounted) {
          setLoadingRoles(false);
        }
      }
    };

    void loadRoles();
    return () => {
      mounted = false;
    };
  }, []);

  async function handlePlanSubmit(payload: PlanRequest): Promise<void> {
    setPlanning(true);
    setPageError("");
    try {
      const result = await createPlan(payload);
      setPlan(result);
      setTimeout(() => {
        const summary = document.getElementById("plan-summary");
        if (summary) {
          summary.scrollIntoView({ behavior: "smooth", block: "start" });
        } else {
          planRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
        }
      }, 150);
    } catch (error) {
      setPageError(error instanceof Error ? error.message : copy.errors.planFailed);
    } finally {
      setPlanning(false);
    }
  }

  function handleScrollToIntake(): void {
    document.getElementById("intake-section")?.scrollIntoView({ behavior: "smooth" });
  }

  return (
    <main className="app-shell">
      <div className="background-noise" aria-hidden />

      <div className="story-band">
        <div className="story-band__inner">
          {/* Hero */}
          <header className="hero panel">
            <p className="eyebrow">{copy.landing.eyebrow}</p>
            <h1>{copy.landing.headline}</h1>
            <p>{copy.landing.support}</p>
          </header>

          {/* 3-step visual */}
          <div className="landing-steps">
            <div className="landing-step">
              <span className="landing-step__number">1</span>
              <span className="landing-step__label">{copy.landing.steps.one}</span>
            </div>
            <div className="landing-step">
              <span className="landing-step__number">2</span>
              <span className="landing-step__label">{copy.landing.steps.two}</span>
            </div>
            <div className="landing-step">
              <span className="landing-step__number">3</span>
              <span className="landing-step__label">{copy.landing.steps.three}</span>
            </div>
          </div>

          {/* Differentiators */}
          <div className="landing-differentiators">
            {(["grounded", "prerequisite", "explainable"] as const).map((key) => (
              <Card key={key}>
                <div className="landing-diff-card">
                  <h3>{copy.landing.differentiators[key].title}</h3>
                  <p>{copy.landing.differentiators[key].body}</p>
                </div>
              </Card>
            ))}
          </div>

          {/* Primary CTA */}
          <button
            type="button"
            className="ui-btn ui-btn--primary"
            onClick={handleScrollToIntake}
            style={{ justifySelf: "center" }}
          >
            {copy.landing.cta}
          </button>
        </div>
      </div>

      {pageError ? <Alert variant="error">{pageError}</Alert> : null}

      <div className="story-band" id="intake-section">
        <div className="story-band__inner">
          <IntakeForm
            roles={roles}
            loadingRoles={loadingRoles}
            planning={planning}
            onSubmit={handlePlanSubmit}
          />
        </div>
      </div>

      <div className="story-band" ref={planRef}>
        <div className="story-band__inner">
          {plan ? (
            <PlanDashboard plan={plan} />
          ) : (
            <section className="panel">
              <EmptyState
                title={copy.empty.noPlanTitle}
                body={copy.empty.noPlanBody}
              />
            </section>
          )}
        </div>
      </div>
    </main>
  );
}
