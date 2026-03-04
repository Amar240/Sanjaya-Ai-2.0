"use client";

import { type FormEvent, useEffect, useMemo, useRef, useState } from "react";

import { ProgressStepper } from "@/components/ui";
import { copy } from "@/lib/copy";
import type {
  PlanMode,
  PlanRequest,
  ProgramLevel,
  RoleOption,
  Term
} from "@/lib/types";

type IntakeFormProps = {
  roles: RoleOption[];
  loadingRoles: boolean;
  planning: boolean;
  onSubmit: (payload: PlanRequest) => Promise<void> | void;
};

function parseCsv(input: string): string[] {
  return input
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

const STEPS = [
  { label: copy.intake.step1Title },
  { label: copy.intake.step2Title },
  { label: copy.intake.step3Title },
];

export default function IntakeForm({
  roles,
  loadingRoles,
  planning,
  onSubmit
}: IntakeFormProps): JSX.Element {
  const [step, setStep] = useState<0 | 1 | 2>(0);
  const [level, setLevel] = useState<ProgramLevel>("UG");
  const [mode, setMode] = useState<PlanMode>("CORE");
  const [goalType, setGoalType] = useState<"select_role" | "type_role" | "explore">("select_role");
  const [confidenceLevel, setConfidenceLevel] = useState<"low" | "medium" | "high">("medium");
  const [hoursPerWeek, setHoursPerWeek] = useState<number>(6);
  const [currentSemester, setCurrentSemester] = useState<number>(1);
  const [startTerm, setStartTerm] = useState<Term>("Fall");
  const [includeOptionalTerms, setIncludeOptionalTerms] = useState<boolean>(false);
  const [minCredits, setMinCredits] = useState<number>(12);
  const [targetCredits, setTargetCredits] = useState<number>(15);
  const [maxCredits, setMaxCredits] = useState<number>(17);
  const [degreeTotalCredits, setDegreeTotalCredits] = useState<number>(128);
  const [selectedInterests, setSelectedInterests] = useState<Set<string>>(new Set());
  const [interestsText, setInterestsText] = useState<string>("");
  const [fusionDomainText, setFusionDomainText] = useState<string>("");
  const [completedCoursesText, setCompletedCoursesText] = useState<string>("");
  const [preferredRoleId, setPreferredRoleId] = useState<string>("");
  const [requestedRoleText, setRequestedRoleText] = useState<string>("");
  const [localError, setLocalError] = useState<string>("");
  const requestedRoleRef = useRef<HTMLInputElement | null>(null);

  const roleOptions = useMemo(() => {
    if (mode !== "FUSION") {
      return roles;
    }
    return roles.filter((role) => role.fusion_available);
  }, [mode, roles]);

  useEffect(() => {
    if (roleOptions.length === 0) {
      setPreferredRoleId("");
      return;
    }
    if (goalType === "explore") {
      return;
    }
    if (!preferredRoleId || !roleOptions.some((role) => role.role_id === preferredRoleId)) {
      setPreferredRoleId(roleOptions[0].role_id);
    }
  }, [goalType, roleOptions, preferredRoleId]);

  useEffect(() => {
    if (goalType === "type_role") {
      requestedRoleRef.current?.focus();
    }
  }, [goalType]);

  function handleLevelChange(nextLevel: ProgramLevel): void {
    setLevel(nextLevel);
    if (nextLevel === "UG") {
      setMinCredits(12);
      setTargetCredits(15);
      setMaxCredits(17);
    } else {
      setMinCredits(9);
      setTargetCredits(9);
      setMaxCredits(12);
    }
  }

  function toggleInterest(label: string): void {
    setSelectedInterests((prev) => {
      const next = new Set(prev);
      if (next.has(label)) {
        next.delete(label);
      } else {
        next.add(label);
      }
      return next;
    });
  }

  const submitDisabled = planning || loadingRoles || roleOptions.length === 0;

  const helperText = useMemo(() => {
    if (loadingRoles) {
      return copy.intake.loadingRoles;
    }
    if (!roleOptions.length) {
      return copy.intake.noRoles;
    }
    if (mode === "FUSION") {
      return copy.intake.fusionRolesLoaded(roleOptions.length);
    }
    return copy.intake.coreRolesLoaded(roleOptions.length);
  }, [loadingRoles, roleOptions.length, mode]);

  const step1Valid =
    targetCredits >= minCredits &&
    targetCredits <= maxCredits &&
    minCredits <= maxCredits &&
    degreeTotalCredits >= 1 &&
    degreeTotalCredits <= 200;

  function handleNext(): void {
    setLocalError("");
    if (step === 0) {
      if (!step1Valid) {
        setLocalError(copy.intake.validationCredits);
        return;
      }
      setStep(1);
    } else if (step === 1) {
      setStep(2);
    }
  }

  function handleBack(): void {
    setLocalError("");
    setStep((s) => (s === 0 ? 0 : (s - 1) as 0 | 1 | 2));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLocalError("");

    if (targetCredits < minCredits || targetCredits > maxCredits) {
      setLocalError(copy.intake.validationCredits);
      return;
    }
    if (degreeTotalCredits < 1 || degreeTotalCredits > 200) {
      setLocalError(copy.intake.validationDegreeTotal);
      return;
    }

    const interestsFromChips = Array.from(selectedInterests);
    const interestsFromText = parseCsv(interestsText);
    const interests = [...new Set([...interestsFromChips, ...interestsFromText])];

    const payload: PlanRequest = {
      student_profile: {
        level,
        mode,
        goal_type: goalType,
        confidence_level: confidenceLevel,
        hours_per_week: hoursPerWeek,
        fusion_domain: mode === "FUSION" ? fusionDomainText.trim() || null : null,
        current_semester: currentSemester,
        start_term: startTerm,
        include_optional_terms: includeOptionalTerms,
        completed_courses: parseCsv(completedCoursesText),
        min_credits: minCredits,
        target_credits: targetCredits,
        max_credits: maxCredits,
        degree_total_credits: degreeTotalCredits,
        interests
      },
      preferred_role_id: goalType === "type_role" ? null : preferredRoleId || null,
      requested_role_text: requestedRoleText.trim() || null
    };

    await onSubmit(payload);
  }

  const preferredRoleTitle = (roleOptions.find((r) => r.role_id === preferredRoleId)?.title ?? preferredRoleId) || "—";

  return (
    <section className="panel intake-panel" id="intake-section">
      <div className="panel-header">
        <h2>{copy.intake.sectionTitle}</h2>
      </div>

      <ProgressStepper steps={STEPS} currentStep={step} />

      <form onSubmit={handleSubmit} className="intake-form intake-form--stepper">
        {localError ? <p className="error-line">{localError}</p> : null}

        {/* Step 0: About you */}
        {step === 0 && (
          <div className="intake-step-content" key="step0">
            <div className="field-grid">
              <label>
                {copy.intake.levelLabel}
                <select
                  value={level}
                  onChange={(e) => handleLevelChange(e.target.value as ProgramLevel)}
                >
                  <option value="UG">{copy.intake.levelUG}</option>
                  <option value="GR">{copy.intake.levelGR}</option>
                </select>
              </label>
              <label>
                {copy.intake.modeLabel}
                <select
                  value={mode}
                  onChange={(e) => setMode(e.target.value as PlanMode)}
                >
                  <option value="CORE">{copy.intake.modeCore}</option>
                  <option value="FUSION">{copy.intake.modeFusion}</option>
                </select>
              </label>
            </div>
            <div className="field-grid">
              <label>
                Current Semester
                <input
                  type="number"
                  min={1}
                  max={12}
                  value={currentSemester}
                  onChange={(e) => setCurrentSemester(Number(e.target.value))}
                  required
                />
              </label>
              <label>
                Start Term
                <select
                  value={startTerm}
                  onChange={(e) => setStartTerm(e.target.value as Term)}
                >
                  <option value="Fall">Fall</option>
                  <option value="Spring">Spring</option>
                  <option value="Summer">Summer</option>
                  <option value="Winter">Winter</option>
                </select>
              </label>
              <label className="checkbox-line">
                <input
                  type="checkbox"
                  checked={includeOptionalTerms}
                  onChange={(e) => setIncludeOptionalTerms(e.target.checked)}
                />
                Include Summer/Winter terms
              </label>
            </div>
            <div className="field-grid three">
              <label>
                Min Credits
                <input
                  type="number"
                  min={0}
                  max={30}
                  value={minCredits}
                  onChange={(e) => setMinCredits(Number(e.target.value))}
                  required
                />
              </label>
              <label>
                Target Credits
                <input
                  type="number"
                  min={0}
                  max={30}
                  value={targetCredits}
                  onChange={(e) => setTargetCredits(Number(e.target.value))}
                  required
                />
              </label>
              <label>
                Max Credits
                <input
                  type="number"
                  min={0}
                  max={30}
                  value={maxCredits}
                  onChange={(e) => setMaxCredits(Number(e.target.value))}
                  required
                />
              </label>
            </div>
            <label>
              {copy.intake.degreeTotalCreditsLabel}
              <input
                type="number"
                min={1}
                max={200}
                value={degreeTotalCredits}
                onChange={(e) => setDegreeTotalCredits(Number(e.target.value))}
                required
              />
              <span className="muted" style={{ display: "block", marginTop: "var(--space-1)", fontSize: "var(--text-xs)" }}>
                {copy.intake.degreeTotalCreditsHelper}
              </span>
            </label>
            <div className="button-group">
              <button
                type="button"
                className="ui-btn ui-btn--primary"
                onClick={handleNext}
                disabled={!step1Valid}
              >
                {copy.intake.nextButton}
              </button>
            </div>
          </div>
        )}

        {/* Step 1: Interests and role */}
        {step === 1 && (
          <div className="intake-step-content" key="step1">
            <label>{copy.intake.interestsLabel}</label>
            <div className="interest-chips">
              {copy.intake.interestSuggestions.map((label) => (
                <button
                  key={label}
                  type="button"
                  className={`ui-chip ${selectedInterests.has(label) ? "ui-chip--success" : ""}`}
                  onClick={() => toggleInterest(label)}
                >
                  {label}
                </button>
              ))}
            </div>
            <label>
              {copy.intake.interestsCustomPlaceholder}
              <input
                type="text"
                value={interestsText}
                onChange={(e) => setInterestsText(e.target.value)}
                placeholder="e.g. ai, finance, cybersecurity"
              />
            </label>

            <p className="muted">{copy.intake.goalQuestion}</p>
            <div className="compact-grid" style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-2)" }}>
              <label className="checkbox-line">
                <input
                  type="radio"
                  name="goal_type"
                  value="select_role"
                  checked={goalType === "select_role"}
                  onChange={() => setGoalType("select_role")}
                />
                {copy.intake.goalSelectRole}
              </label>
              <label className="checkbox-line">
                <input
                  type="radio"
                  name="goal_type"
                  value="type_role"
                  checked={goalType === "type_role"}
                  onChange={() => setGoalType("type_role")}
                />
                {copy.intake.goalTypeRole}
              </label>
              <label className="checkbox-line">
                <input
                  type="radio"
                  name="goal_type"
                  value="explore"
                  checked={goalType === "explore"}
                  onChange={() => setGoalType("explore")}
                />
                {copy.intake.goalExplore}
              </label>
            </div>

            {goalType !== "type_role" && (
              <>
                <label>
                  Preferred Role{goalType === "explore" ? " (optional)" : ""}
                  <select
                    value={preferredRoleId}
                    onChange={(e) => setPreferredRoleId(e.target.value)}
                    disabled={loadingRoles || roleOptions.length === 0}
                  >
                    {goalType === "explore" ? <option value="">No preference yet</option> : null}
                    {roleOptions.map((role) => (
                      <option key={role.role_id} value={role.role_id}>
                        {role.title}
                      </option>
                    ))}
                  </select>
                </label>
                <p className="muted">{helperText}</p>
              </>
            )}

            {mode === "FUSION" && (
              <>
                <label>
                  {copy.intake.fusionDomainLabel}
                  <input
                    type="text"
                    value={fusionDomainText}
                    onChange={(e) => setFusionDomainText(e.target.value)}
                    placeholder={copy.intake.fusionDomainPlaceholder}
                  />
                </label>
                <p className="muted">{copy.intake.fusionDomainHelper}</p>
              </>
            )}

            {goalType === "type_role" ? (
              <label>
                Role I&apos;m Looking For
                <input
                  ref={requestedRoleRef}
                  type="text"
                  value={requestedRoleText}
                  onChange={(e) => setRequestedRoleText(e.target.value)}
                  placeholder="e.g. AI policy architect"
                />
              </label>
            ) : (
              <label>
                Role I&apos;m Looking For (optional)
                <input
                  ref={requestedRoleRef}
                  type="text"
                  value={requestedRoleText}
                  onChange={(e) => setRequestedRoleText(e.target.value)}
                  placeholder="e.g. AI policy architect"
                />
              </label>
            )}

            <div className="field-grid three">
              <label>
                Confidence Level
                <select
                  value={confidenceLevel}
                  onChange={(e) => setConfidenceLevel(e.target.value as "low" | "medium" | "high")}
                >
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                </select>
              </label>
              <label>
                Hours/Week For Projects
                <input
                  type="number"
                  min={0}
                  max={40}
                  value={hoursPerWeek}
                  onChange={(e) => setHoursPerWeek(Number(e.target.value))}
                />
              </label>
            </div>

            <label>
              Completed Courses (comma-separated IDs)
              <input
                type="text"
                value={completedCoursesText}
                onChange={(e) => setCompletedCoursesText(e.target.value)}
                placeholder="CISC-108, MATH-201"
              />
            </label>

            <div className="button-group">
              <button type="button" className="ui-btn ui-btn--secondary" onClick={handleBack}>
                {copy.intake.backButton}
              </button>
              <button type="button" className="ui-btn ui-btn--primary" onClick={handleNext}>
                {copy.intake.nextButton}
              </button>
            </div>
          </div>
        )}

        {/* Step 2: Review and generate */}
        {step === 2 && (
          <div className="intake-step-content" key="step2">
            <div className="review-card ui-card">
              <p><strong>Level:</strong> {level === "UG" ? copy.intake.levelUG : copy.intake.levelGR}</p>
              <p><strong>Mode:</strong> {mode === "CORE" ? copy.intake.modeCore : copy.intake.modeFusion}</p>
              <p><strong>Semester:</strong> {currentSemester} · {startTerm}</p>
              <p><strong>Credits:</strong> {minCredits} – {targetCredits} – {maxCredits}</p>
              <p><strong>Interests:</strong> {[...selectedInterests, ...parseCsv(interestsText)].filter(Boolean).join(", ") || "—"}</p>
              <p><strong>Goal:</strong> {goalType === "select_role" ? copy.intake.goalSelectRole : goalType === "type_role" ? copy.intake.goalTypeRole : copy.intake.goalExplore}</p>
              <p><strong>Role:</strong> {preferredRoleTitle}</p>
              {mode === "FUSION" && fusionDomainText.trim() && (
                <p><strong>Fusion domain:</strong> {fusionDomainText.trim()}</p>
              )}
            </div>
            <div className="button-group">
              <button type="button" className="ui-btn ui-btn--secondary" onClick={handleBack}>
                {copy.intake.backButton}
              </button>
              <button type="submit" disabled={submitDisabled} className="ui-btn ui-btn--primary">
                {planning ? copy.intake.submitLoading : copy.intake.submitButton}
              </button>
            </div>
          </div>
        )}
      </form>
    </section>
  );
}
