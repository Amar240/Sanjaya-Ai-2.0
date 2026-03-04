"use client";

import { useMemo, useState } from "react";

import AdvisorQAPanel from "@/components/AdvisorQAPanel";
import CareerPathMap from "@/components/CareerPathMap";
import CourseQADialog from "@/components/CourseQADialog";
import EvidenceRef from "@/components/EvidenceRef";
import PlanDashboardNav, { type DashboardSectionKey } from "@/components/PlanDashboardNav";
import PlanSummaryBar from "@/components/PlanSummaryBar";
import { generateStoryboard, matchJobPosting } from "@/lib/api";
import { copy } from "@/lib/copy";
import { formatSkillId, skillDisplayLabel } from "@/lib/skillLabels";
import { explainWhyMatters, getValidationLabel, suggestActions } from "@/lib/warningCopy";
import type {
  CoursePurposeCard,
  EvidencePanelItem,
  JobMatchResponse,
  PlanError,
  PlanResponse,
  SkillCoverage,
  StoryboardResponse,
} from "@/lib/types";

type PlanDashboardProps = {
  plan: PlanResponse;
};

const ERROR_CODES = new Set<string>([
  "COURSE_NOT_FOUND",
  "PREREQ_ORDER",
  "CREDIT_OVER_MAX",
  "LEVEL_MISMATCH",
]);

const JOB_PRESET_ONE = `AI Engineer Intern
Required: Python, SQL, machine learning fundamentals, statistics, data wrangling, version control.
Preferred: deep learning with PyTorch or TensorFlow, cloud ML services (AWS SageMaker, GCP Vertex AI, or Azure ML), experiment tracking.
Tools: Python, SQL, Jupyter, Git, Docker, one major cloud platform (AWS, GCP, or Azure).`;

const JOB_PRESET_TWO = `Cybersecurity Analyst
Required: network security fundamentals, Linux administration, incident response, log analysis, risk management.
Preferred: scripting with Python, common security frameworks and controls (NIST, ISO 27001, CIS), cloud security basics.
Tools: SIEM platforms, Linux CLI, vulnerability scanners, ticketing systems, Python.`;

function percentCovered(plan: PlanResponse): number {
  if (!plan.skill_coverage.length) {
    return 0;
  }
  const covered = plan.skill_coverage.filter((skill) => skill.covered).length;
  return Math.round((covered / plan.skill_coverage.length) * 100);
}

function courseCardKey(card: CoursePurposeCard, idx: number): string {
  return `${card.course_id}-${idx}`;
}

function skillLine(skill: SkillCoverage): string {
  if (!skill.matched_courses.length) {
    return "No mapped courses";
  }
  return skill.matched_courses.join(", ");
}

function anchorId(prefix: string, raw: string): string {
  return `${prefix}-${raw.replace(/[^a-zA-Z0-9_-]/g, "-")}`;
}

function errorSeverity(error: PlanError): "warning" | "error" {
  const severity = String(error.details?.severity ?? "").toLowerCase();
  if (severity === "warning") {
    return "warning";
  }
  if (severity === "error") {
    return "error";
  }
  return ERROR_CODES.has(error.code) ? "error" : "warning";
}

export default function PlanDashboard({ plan }: PlanDashboardProps): JSX.Element {
  const coveragePct = percentCovered(plan);
  const [filterSelectedSkills, setFilterSelectedSkills] = useState<boolean>(false);
  const [queuedAdvisorQuestion, setQueuedAdvisorQuestion] = useState<string | null>(null);
  const [queuedAdvisorNonce, setQueuedAdvisorNonce] = useState<number>(0);
  const [advisorFocusNonce, setAdvisorFocusNonce] = useState<number>(0);
  const [brainTab, setBrainTab] = useState<"reality" | "gap" | "fusion" | "storyboard" | "jobcheck">("reality");
  const [storyboardTone, setStoryboardTone] = useState<"friendly" | "concise">("friendly");
  const [storyboardAudience, setStoryboardAudience] = useState<
    "beginner" | "intermediate"
  >("beginner");
  const [storyboardLoading, setStoryboardLoading] = useState<boolean>(false);
  const [storyboardError, setStoryboardError] = useState<string>("");
  const [storyboard, setStoryboard] = useState<StoryboardResponse | null>(null);
  const [jobText, setJobText] = useState<string>("");
  const [jobMatchLoading, setJobMatchLoading] = useState<boolean>(false);
  const [jobMatchError, setJobMatchError] = useState<string>("");
  const [jobMatch, setJobMatch] = useState<JobMatchResponse | null>(null);
  const [expandedIssueGroups, setExpandedIssueGroups] = useState<Record<string, boolean>>({});
  const [expandedValidationItems, setExpandedValidationItems] = useState<Record<string, boolean>>({});
  const [selectedCourse, setSelectedCourse] = useState<{
    courseId: string;
    courseTitle: string;
  } | null>(null);
  const [activeSection, setActiveSection] = useState<DashboardSectionKey>("path");

  const selectedSkillIds = useMemo(
    () => new Set(plan.skill_coverage.map((skill) => skill.required_skill_id)),
    [plan.skill_coverage]
  );

  const courseTitleById = useMemo(() => {
    const map: Record<string, string> = {};
    for (const card of plan.course_purpose_cards ?? []) {
      map[card.course_id] = card.course_title;
    }
    return map;
  }, [plan.course_purpose_cards]);

  const filteredEvidence = useMemo(() => {
    const evidence = plan.evidence_panel || [];
    if (!filterSelectedSkills) {
      return evidence;
    }
    return evidence.filter((item) => selectedSkillIds.has(item.skill_id));
  }, [filterSelectedSkills, plan.evidence_panel, selectedSkillIds]);

  const groupedValidation = useMemo(() => {
    const groups = new Map<
      string,
      { code: string; severity: "warning" | "error"; items: PlanError[] }
    >();
    for (const error of plan.validation_errors) {
      const severity = errorSeverity(error);
      const key = `${error.code}|${severity}`;
      const existing = groups.get(key);
      if (existing) {
        existing.items.push(error);
      } else {
        groups.set(key, { code: error.code, severity, items: [error] });
      }
    }
    return Array.from(groups.values()).sort((a, b) => {
      if (a.severity !== b.severity) {
        return a.severity === "error" ? -1 : 1;
      }
      return a.code.localeCompare(b.code);
    });
  }, [plan.validation_errors]);

  const sourceById = useMemo(() => {
    const rows = new Map<string, { provider: string; title: string; url: string }>();
    for (const item of plan.evidence_panel || []) {
      if (!rows.has(item.source_id)) {
        rows.set(item.source_id, {
          provider: item.source_provider,
          title: item.source_title,
          url: item.source_url,
        });
      }
    }
    for (const card of plan.course_purpose_cards || []) {
      for (const item of card.evidence || []) {
        if (!rows.has(item.source_id)) {
          rows.set(item.source_id, {
            provider: item.source_provider,
            title: item.source_title,
            url: item.source_url,
          });
        }
      }
    }
    return rows;
  }, [plan.course_purpose_cards, plan.evidence_panel]);

  const evidenceById = useMemo(() => {
    const rows = new Map<string, EvidencePanelItem>();
    for (const item of plan.evidence_panel || []) {
      if (!rows.has(item.evidence_id)) {
        rows.set(item.evidence_id, item);
      }
    }
    return rows;
  }, [plan.evidence_panel]);

  function handleAskWhyNotRole(roleId: string, roleTitle: string): void {
    const question = `Why not ${roleTitle} (${roleId})?`;
    setQueuedAdvisorQuestion(question);
    setQueuedAdvisorNonce((value) => value + 1);
    handleFocusAdvisor();
  }

  async function handleGenerateStoryboard(): Promise<void> {
    setStoryboardLoading(true);
    setStoryboardError("");
    try {
      const res = await generateStoryboard({
        plan_id: plan.plan_id,
        tone: storyboardTone,
        audience_level: storyboardAudience,
      });
      setStoryboard(res);
    } catch (error) {
      setStoryboardError(
        error instanceof Error ? error.message : "Failed to generate storyboard."
      );
    } finally {
      setStoryboardLoading(false);
    }
  }

  async function handleExtractJobMatch(): Promise<void> {
    if (jobText.trim().length < 50) {
      setJobMatchError("Please paste at least 50 characters from a job posting.");
      return;
    }
    setJobMatchLoading(true);
    setJobMatchError("");
    try {
      const response = await matchJobPosting({
        text: jobText.trim(),
        plan_id: plan.plan_id || null,
      });
      setJobMatch(response);
    } catch (error) {
      setJobMatchError(error instanceof Error ? error.message : "Job match failed.");
    } finally {
      setJobMatchLoading(false);
    }
  }

  function scrollTo(id: string): void {
    const node = document.getElementById(id);
    if (!node) {
      return;
    }
    node.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function handleViewReality(): void {
    setActiveSection("path");
    setBrainTab("reality");
    scrollTo("brain-picture");
  }

  function handleFixGaps(): void {
    setActiveSection("path");
    setBrainTab("gap");
    scrollTo("brain-picture");
  }

  function handleGenerateStoryboardFromBar(): void {
    setActiveSection("path");
    setBrainTab("storyboard");
    scrollTo("brain-picture");
    void handleGenerateStoryboard();
  }

  function handleFocusAdvisor(): void {
    setActiveSection("advisor");
    setAdvisorFocusNonce((value) => value + 1);
  }

  function toggleIssueGroup(key: string): void {
    setExpandedIssueGroups((prev) => ({ ...prev, [key]: !prev[key] }));
  }

  const showJobMatchDemoHint = useMemo(() => {
    if (!jobMatch) {
      return false;
    }
    return (
      jobMatch.mapped_skills.length < 5 ||
      jobMatch.unmapped_terms.length >= 3 ||
      (jobMatch.recommended_projects.length === 0 && jobMatch.missing_skill_ids.length > 0)
    );
  }, [jobMatch]);

  const firstCourseAnchorById = new Set<string>();

  return (
    <section className="panel dashboard-panel">
      <div className="plan-head">
        <div>
          <p className="eyebrow">Selected Role</p>
          <h2>{plan.selected_role_title}</h2>
        </div>
        <div className="kpi-card">
          <span>Skill Coverage</span>
          <strong>{coveragePct}%</strong>
        </div>
      </div>

      <div className="plan-dashboard__summary-wrap" id="plan-summary">
        <PlanSummaryBar
          plan={plan}
          onViewReality={handleViewReality}
          onFixGaps={handleFixGaps}
          onGenerateStoryboard={handleGenerateStoryboardFromBar}
          onAskAdvisor={handleFocusAdvisor}
          storyboardLoading={storyboardLoading}
        />
      </div>
      <PlanDashboardNav activeSection={activeSection} onSectionChange={setActiveSection} />
      <div className="plan-dashboard__content">
        {activeSection === "path" ? (
          <div
            id="dashboard-section-path"
            role="tabpanel"
            aria-labelledby="tab-path"
            className="dashboard-section-panel"
          >
      {/* Plan Hero */}
      <div className="ui-section-header" style={{ textAlign: "center" }}>
        <h2 className="ui-section-header__title" style={{ fontSize: "clamp(var(--text-xl), 3vw, var(--text-hero))" }}>
          {copy.plan.heroPath(plan.selected_role_title)}
        </h2>
        <p className="ui-section-header__desc">{copy.plan.heroSupport}</p>
      </div>

      <article className="subpanel" id="brain-picture">
        <h3>{copy.brainPicture.sectionTitle}</h3>
        <div className="tab-row">
          <button
            type="button"
            className={`tab-btn ${brainTab === "reality" ? "active" : ""}`}
            onClick={() => setBrainTab("reality")}
          >
            {copy.brainPicture.step1Tab}
          </button>
          <button
            type="button"
            className={`tab-btn ${brainTab === "gap" ? "active" : ""}`}
            onClick={() => setBrainTab("gap")}
          >
            {copy.brainPicture.step2Tab}
          </button>
          {(plan.fusion_summary ?? plan.fusion_pack_summary) ? (
            <button
              type="button"
              className={`tab-btn ${brainTab === "fusion" ? "active" : ""}`}
              onClick={() => setBrainTab("fusion")}
            >
              {copy.brainPicture.step3Tab}
            </button>
          ) : null}
          <button
            type="button"
            className={`tab-btn ${brainTab === "storyboard" ? "active" : ""}`}
            onClick={() => setBrainTab("storyboard")}
          >
            {copy.brainPicture.step4Tab}
          </button>
          <button
            type="button"
            className={`tab-btn ${brainTab === "jobcheck" ? "active" : ""}`}
            onClick={() => setBrainTab("jobcheck")}
          >
            {copy.brainPicture.step5Tab}
          </button>
        </div>
        {!(plan.fusion_summary ?? plan.fusion_pack_summary) ? (
          <p className="muted" style={{ fontSize: "var(--text-xs)", marginBottom: "var(--space-2)" }}>
            {copy.brainPicture.step3HiddenNote}
          </p>
        ) : null}

        {brainTab === "reality" ? (
          plan.role_reality ? (
            <div className="brain-content" key={brainTab}>
              <p>
                <strong>{plan.role_reality.role_title}</strong> (USA)
              </p>
              <ul className="plain-list">
                {plan.role_reality.typical_tasks.map((task, idx) => (
                  <li key={`${task}-${idx}`}>{task}</li>
                ))}
              </ul>
              <p className="muted">
                Salary range (USD):{" "}
                <strong>
                  {plan.role_reality.salary_usd.p25
                    ? `$${plan.role_reality.salary_usd.p25.toLocaleString()}`
                    : "n/a"}
                  {" - "}
                  {plan.role_reality.salary_usd.median
                    ? `$${plan.role_reality.salary_usd.median.toLocaleString()}`
                    : "n/a"}
                  {" - "}
                  {plan.role_reality.salary_usd.p75
                    ? `$${plan.role_reality.salary_usd.p75.toLocaleString()}`
                    : "n/a"}
                </strong>
              </p>
              <p className="muted">{copy.brainPicture.step1SalaryNote}</p>
              <ul className="plain-list">
                {plan.role_reality.sources.map((sourceId) => {
                  const meta = sourceById.get(sourceId);
                  return (
                    <li key={`reality-source-${sourceId}`}>
                      {meta ? (
                        <a href={meta.url} target="_blank" rel="noreferrer">
                          {meta.provider}: {meta.title} ({sourceId})
                        </a>
                      ) : (
                        <span className="mono">{sourceId}</span>
                      )}
                    </li>
                  );
                })}
              </ul>
            </div>
          ) : (
            <p className="muted">{copy.brainPicture.step1Empty}</p>
          )
        ) : null}

        {brainTab === "gap" ? (
          plan.gap_report ? (
            <div className="brain-content" key={brainTab}>
              <p className="muted">
                Missing skills: <strong>{plan.gap_report.missing_skills.length}</strong> |
                Covered: <strong> {plan.gap_report.covered_skills.length}</strong>
              </p>
              {plan.gap_report.missing_skills.length ? (
                <div className="cards-grid">
                  {plan.gap_report.missing_skills.map((item) => (
                    <div className="purpose-card" key={`gap-${item.skill_id}`}>
                      <p>
                        <strong>{skillDisplayLabel(item.skill_id, item.skill_name)}</strong>
                      </p>
                      <p className="muted">{item.reason}</p>
                      <ul className="plain-list">
                        {item.recommended_projects.map((project) => (
                          <li key={project.template_id}>
                            <p>
                              <strong>{project.title}</strong> - {project.level} (
                              {project.time_hours}h){" "}
                              <span className={`issue-pill ${project.effort_fit === "fits" ? "warning" : "error"}`}>
                                {project.effort_fit}
                              </span>
                            </p>
                            {project.deliverables.length ? (
                              <p className="muted">
                                Deliverables: {project.deliverables.join("; ")}
                              </p>
                            ) : null}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="muted">{copy.brainPicture.step2AllCovered}</p>
              )}
            </div>
          ) : (
            <p className="muted">{copy.brainPicture.step2Empty}</p>
          )
        ) : null}

        {brainTab === "fusion" ? (
          <div className="brain-content" key={brainTab}>
            {plan.fusion_pack_summary ? (
              <>
                <p>
                  <strong>{plan.fusion_pack_summary.title}</strong>
                </p>
                <p className="muted">
                  Domains: {plan.fusion_pack_summary.domain_a} + {plan.fusion_pack_summary.domain_b}
                </p>
                <p className="muted">
                  Target roles: {plan.fusion_pack_summary.target_roles.join(", ")}
                </p>
                <div className="grid-two">
                  <div>
                    <h4>Unlock Skills</h4>
                    <ul className="plain-list">
                      {plan.fusion_pack_summary.unlock_skills.map((skillId) => (
                        <li key={`pack-skill-${skillId}`} className="mono">
                          {skillId}
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <h4>Starter Projects</h4>
                    <ul className="plain-list">
                      {plan.fusion_pack_summary.starter_projects.map((projectId) => (
                        <li key={`pack-project-${projectId}`} className="mono">
                          {projectId}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              </>
            ) : plan.fusion_summary ? (
              <>
                <p className="muted">{copy.brainPicture.step3Empty}</p>
                <ul className="plain-list">
                  {plan.fusion_summary.unlock_skills.map((item) => (
                    <li key={`unlock-${item.skill_id}`}>
                      {formatSkillId(item.skill_id)} — {item.reason}
                    </li>
                  ))}
                </ul>
              </>
            ) : (
              <p className="muted">{copy.brainPicture.step3Empty}</p>
            )}
          </div>
        ) : null}

        {brainTab === "storyboard" ? (
          <div className="brain-content" key={brainTab}>
            <div className="storyboard-controls">
              <label>
                Tone
                <select
                  value={storyboardTone}
                  onChange={(event) =>
                    setStoryboardTone(event.target.value as "friendly" | "concise")
                  }
                  disabled={storyboardLoading}
                >
                  <option value="friendly">Friendly</option>
                  <option value="concise">Concise</option>
                </select>
              </label>
              <label>
                Audience
                <select
                  value={storyboardAudience}
                  onChange={(event) =>
                    setStoryboardAudience(
                      event.target.value as "beginner" | "intermediate"
                    )
                  }
                  disabled={storyboardLoading}
                >
                  <option value="beginner">Beginner</option>
                  <option value="intermediate">Intermediate</option>
                </select>
              </label>
              <button
                type="button"
                className="btn-primary"
                onClick={() => void handleGenerateStoryboard()}
                disabled={storyboardLoading}
              >
                {storyboardLoading ? "Generating..." : "Generate Storyboard"}
              </button>
            </div>
            {storyboardError ? <p className="error-line">{storyboardError}</p> : null}
            {storyboard ? (
              <div className="cards-grid">
                {storyboard.sections.map((section, idx) => (
                  <div className="purpose-card" key={`storyboard-${idx}-${section.title}`}>
                    <p>
                      <strong>{section.title}</strong>
                    </p>
                    <p>{section.body}</p>
                    {section.citations.length ? (
                      <div className="storyboard-citations">
                        {section.citations.map((citation, citationIdx) => {
                          if (citation.kind === "evidence_id") {
                            const evidence = evidenceById.get(citation.id);
                            return evidence ? (
                              <EvidenceRef
                                key={`${section.title}-ev-${citation.id}-${citationIdx}`}
                                evidence={evidence}
                                compact
                              />
                            ) : (
                              <p
                                className="muted mono"
                                key={`${section.title}-ev-missing-${citation.id}-${citationIdx}`}
                              >
                                Evidence unavailable: {citation.id}
                              </p>
                            );
                          }
                          const source = sourceById.get(citation.id);
                          return source ? (
                            <a
                              key={`${section.title}-src-${citation.id}-${citationIdx}`}
                              href={source.url}
                              target="_blank"
                              rel="noreferrer"
                              className="story-source-link"
                            >
                              {source.provider}: {source.title}
                            </a>
                          ) : (
                            <p
                              className="muted mono"
                              key={`${section.title}-src-missing-${citation.id}-${citationIdx}`}
                            >
                              Source: {citation.id}
                            </p>
                          );
                        })}
                      </div>
                    ) : null}
                  </div>
                ))}
              </div>
            ) : (
              <p className="muted">{copy.brainPicture.step4Placeholder}</p>
            )}
          </div>
        ) : null}

        {brainTab === "jobcheck" ? (
          <div className="brain-content" key={brainTab}>
            <p className="muted">
              Paste a real job posting or use the presets to try an AI/Data role or a Cybersecurity role. We extract skills and compare them to your roadmap. This is guidance, not a job guarantee.
            </p>
            <div className="storyboard-controls">
              <button
                type="button"
                className="btn-secondary"
                onClick={() => setJobText(JOB_PRESET_ONE)}
              >
                Load AI / Data job
              </button>
              <button
                type="button"
                className="btn-secondary"
                onClick={() => setJobText(JOB_PRESET_TWO)}
              >
                Load Cybersecurity job
              </button>
            </div>
            <label>
              Paste Job Description
              <textarea
                value={jobText}
                onChange={(event) => setJobText(event.target.value)}
                rows={8}
                placeholder="Paste a USA job posting text here..."
              />
            </label>
            <button
              type="button"
              className="btn-primary"
              disabled={jobMatchLoading}
              onClick={() => void handleExtractJobMatch()}
            >
              {jobMatchLoading ? "Extracting..." : "Extract & Match"}
            </button>
            {jobMatchError ? <p className="error-line">{jobMatchError}</p> : null}
            {jobMatch ? (
              <div className="cards-grid">
                <div className="purpose-card">
                  <p>
                    <strong>{jobMatch.job_title || "Untitled Job Posting"}</strong>
                  </p>
                  <p className="muted">{jobMatch.disclaimer}</p>
                  <p className="muted">
                    Mapping summary: mapped {jobMatch.mapping_summary.mapped_count}, unmapped{" "}
                    {jobMatch.mapping_summary.unmapped_count}, threshold{" "}
                    {jobMatch.mapping_summary.threshold_used}
                  </p>
                  {showJobMatchDemoHint ? (
                    <p className="muted">
                      For the demo, results are strongest for our demo-tier roles.
                    </p>
                  ) : null}
                </div>

                <div className="purpose-card">
                  <p><strong>What this job asks for</strong></p>
                  <p className="muted">Required: {jobMatch.extracted.required_skills.join(", ") || "None"}</p>
                  <p className="muted">Preferred: {jobMatch.extracted.preferred_skills.join(", ") || "None"}</p>
                  <p className="muted">Tools: {jobMatch.extracted.tools.join(", ") || "None"}</p>
                </div>

                <div className="purpose-card">
                  <p><strong>How we map it to skills</strong></p>
                  <ul className="plain-list">
                    {jobMatch.mapped_skills.map((item) => (
                      <li key={`mapped-${item.skill_id}-${item.source}`}>
                        {formatSkillId(item.skill_id)} ({item.source}) —{" "}
                        {Math.round(item.match_confidence * 100)}%
                        {item.matched_by ? ` via ${item.matched_by}` : ""}
                        {item.matched_on ? ` [${item.matched_on}]` : ""}
                      </li>
                    ))}
                  </ul>
                </div>

                <div className="purpose-card">
                  <p><strong>How it lines up with your roadmap</strong></p>
                  <p className="muted">Covered (in roadmap): {jobMatch.covered_skill_ids.map(formatSkillId).join(", ") || "None"}</p>
                  <p className="muted">Missing (in roadmap scope): {jobMatch.missing_skill_ids.map(formatSkillId).join(", ") || "None"}</p>
                  <p className="muted">Out-of-scope: {jobMatch.out_of_scope_skill_ids.map(formatSkillId).join(", ") || "None"}</p>
                  <p className="muted">Unmapped terms: {jobMatch.unmapped_terms.map((item) => `${item.term} (${item.source})`).join(", ") || "None"}</p>
                </div>

                <div className="purpose-card">
                  <p><strong>Project Recommendations</strong></p>
                  {jobMatch.recommended_projects.length ? (
                    <ul className="plain-list">
                      {jobMatch.recommended_projects.map((skill) => (
                        <li key={`job-project-${skill.skill_id}`}>
                          <p>
                            <strong>{skillDisplayLabel(skill.skill_id, skill.skill_name)}</strong>
                          </p>
                          <ul className="plain-list">
                            {skill.projects.map((project) => (
                              <li key={project.template_id}>
                                {project.title} ({project.level}, {project.time_hours}h){" "}
                                <span className={`issue-pill ${project.effort_fit === "fits" ? "warning" : "error"}`}>
                                  {project.effort_fit}
                                </span>
                              </li>
                            ))}
                          </ul>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="muted">No project recommendations for current missing-skill set.</p>
                  )}
                  {jobMatch.recommended_projects.length ? (
                    <p className="muted">
                      Start with these 1-2 projects first:{" "}
                      {jobMatch.recommended_projects
                        .flatMap((item) => item.projects)
                        .slice(0, 2)
                        .map((item) => item.title)
                        .join(", ") || "No starter projects available."}
                    </p>
                  ) : null}
                </div>
              </div>
            ) : (
              <p className="muted">Paste a posting and run Extract & Match to compare against your roadmap.</p>
            )}
          </div>
        ) : null}
      </article>
          </div>
        ) : null}

        {activeSection === "semesters" ? (
          <div
            id="dashboard-section-semesters"
            role="tabpanel"
            aria-labelledby="tab-semesters"
            className="dashboard-section-panel"
          >
            <article className="subpanel" id="semester-roadmap">
              <h3>Semester Roadmap</h3>
              <div className="timeline-grid">
                {plan.semesters.map((semester) => (
                  <div className="timeline-card" key={`semester-${semester.semester_index}`}>
                    <header>
                      <p className="eyebrow">
                        Semester {semester.semester_index} - {semester.term}
                      </p>
                      <strong>{semester.total_credits} credits</strong>
                    </header>
                    <div className="credit-bar">
                      <div
                        className={`credit-bar__fill ${semester.total_credits > 17 ? "credit-bar__fill--over" : semester.total_credits > 15 ? "credit-bar__fill--heavy" : ""}`}
                        style={{ width: `${Math.min((semester.total_credits / 18) * 100, 100)}%` }}
                      />
                    </div>
                    <ul>
                      {semester.courses.map((courseId) => {
                        const courseAnchor = anchorId("course", courseId);
                        const shouldAnchor = !firstCourseAnchorById.has(courseAnchor);
                        if (shouldAnchor) {
                          firstCourseAnchorById.add(courseAnchor);
                        }
                        return (
                          <li
                            id={shouldAnchor ? courseAnchor : undefined}
                            key={`${semester.semester_index}-${courseId}`}
                            className="course-clickable"
                            role="button"
                            tabIndex={0}
                            onClick={() =>
                              setSelectedCourse({
                                courseId,
                                courseTitle: courseTitleById[courseId] ?? courseId,
                              })
                            }
                            onKeyDown={(e) => {
                              if (e.key === "Enter" || e.key === " ") {
                                e.preventDefault();
                                setSelectedCourse({
                                  courseId,
                                  courseTitle: courseTitleById[courseId] ?? courseId,
                                });
                              }
                            }}
                          >
                            {courseTitleById[courseId]
                              ? `${courseTitleById[courseId]} (${courseId})`
                              : courseId}
                          </li>
                        );
                      })}
                    </ul>
                    {semester.warnings.length ? (
                      <details>
                        <summary>{semester.warnings.length} warning(s)</summary>
                        <ul className="plain-list warning-list">
                          {semester.warnings.map((warning, idx) => (
                            <li key={`${warning}-${idx}`}>{warning}</li>
                          ))}
                        </ul>
                      </details>
                    ) : null}
                  </div>
                ))}
              </div>
            </article>
          </div>
        ) : null}

        {activeSection === "courses" ? (
          <div
            id="dashboard-section-courses"
            role="tabpanel"
            aria-labelledby="tab-courses"
            className="dashboard-section-panel"
          >
            {plan.course_purpose_cards?.length ? (
              <article className="subpanel">
                <h3>Course Purpose Cards</h3>
                <div className="cards-grid">
                  {plan.course_purpose_cards.map((card, idx) => (
                    <div
                      className="purpose-card purpose-card--clickable"
                      key={courseCardKey(card, idx)}
                      role="button"
                      tabIndex={0}
                      onClick={() =>
                        setSelectedCourse({
                          courseId: card.course_id,
                          courseTitle: card.course_title,
                        })
                      }
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          setSelectedCourse({
                            courseId: card.course_id,
                            courseTitle: card.course_title,
                          });
                        }
                      }}
                    >
                      <p><strong>{card.course_id}</strong> — {card.course_title}</p>
                      <p className="purpose-card__why">{card.why_this_course}</p>
                      <div className="skill-tags">
                        {card.satisfied_skills.length ? (
                          card.satisfied_skills.map((skillId) => (
                            <span key={`${card.course_id}-${skillId}`} className="tag">
                              {formatSkillId(skillId)}
                            </span>
                          ))
                        ) : (
                          <span className="tag muted-tag">Support / prerequisite</span>
                        )}
                      </div>
                      {card.evidence.length ? (
                        <details>
                          <summary>Evidence ({card.evidence.length})</summary>
                          <div className="evidence-inline-list">
                            {card.evidence.map((evidence, evidenceIdx) => (
                              <div key={`${card.course_id}-${evidence.source_id}-${evidenceIdx}`}>
                                <p className="muted">{evidence.snippet}</p>
                                <EvidenceRef evidence={evidence} compact />
                              </div>
                            ))}
                          </div>
                        </details>
                      ) : null}
                    </div>
                  ))}
                </div>
              </article>
            ) : null}
          </div>
        ) : null}

        {activeSection === "skills" ? (
          <div
            id="dashboard-section-skills"
            role="tabpanel"
            aria-labelledby="tab-skills"
            className="dashboard-section-panel"
          >
      <CareerPathMap plan={plan} onAskWhyNotRole={handleAskWhyNotRole} />

      {plan.fusion_summary ? (
        <article className="subpanel fusion-panel">
          <h3>Fusion Readiness</h3>
          <p className="muted">
            Domain: <strong>{plan.fusion_summary.domain}</strong> | Weights: domain{" "}
            {Math.round(plan.fusion_summary.domain_weight * 100)}% and tech{" "}
            {Math.round(plan.fusion_summary.tech_weight * 100)}%
          </p>
          <div className="fusion-kpis">
            <div className="kpi-mini">
              <span>Domain Ready</span>
              <strong>{Math.round(plan.fusion_summary.readiness.domain_ready_pct * 100)}%</strong>
            </div>
            <div className="kpi-mini">
              <span>Tech Ready</span>
              <strong>{Math.round(plan.fusion_summary.readiness.tech_ready_pct * 100)}%</strong>
            </div>
            <div className="kpi-mini">
              <span>Overall Fit</span>
              <strong>{Math.round(plan.fusion_summary.readiness.overall_fit_pct * 100)}%</strong>
            </div>
          </div>

          <div className="grid-two">
            <div>
              <h4>Domain Skills</h4>
              <ul className="chip-list">
                {plan.fusion_summary.domain_skill_coverage.map((skill) => (
                  <li key={`domain-${skill.required_skill_id}`} className="chip-item">
                    <span className={skill.covered ? "chip good" : "chip bad"}>
                      {skill.covered ? "Covered" : "Gap"}
                    </span>
                    <div>
                      <p>{formatSkillId(skill.required_skill_id)}</p>
                      <p className="muted">{skillLine(skill)}</p>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h4>Tech Skills</h4>
              <ul className="chip-list">
                {plan.fusion_summary.tech_skill_coverage.map((skill) => (
                  <li key={`tech-${skill.required_skill_id}`} className="chip-item">
                    <span className={skill.covered ? "chip good" : "chip bad"}>
                      {skill.covered ? "Covered" : "Gap"}
                    </span>
                    <div>
                      <p className="mono">{skill.required_skill_id}</p>
                      <p className="muted">{skillLine(skill)}</p>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </article>
      ) : null}

      <article className="subpanel">
          <h3>Skill Coverage</h3>
          <ul className="chip-list">
            {plan.skill_coverage.map((skill) => (
              <li
                id={anchorId("skill", skill.required_skill_id)}
                key={skill.required_skill_id}
                className="chip-item"
              >
                <span className={skill.covered ? "chip good" : "chip bad"}>
                  {skill.covered ? "Covered" : "Gap"}
                </span>
                <div>
                  <p>{formatSkillId(skill.required_skill_id)}</p>
                  <p className="muted">{skillLine(skill)}</p>
                </div>
              </li>
            ))}
          </ul>
        </article>

      {plan.evidence_panel?.length ? (
        <article className="subpanel" id="evidence-panel">
          <h3>Evidence Panel</h3>
          <label className="checkbox-line">
            <input
              type="checkbox"
              checked={filterSelectedSkills}
              onChange={(event) => setFilterSelectedSkills(event.target.checked)}
            />
            <span>Show only selected-plan skills</span>
          </label>
          <ul className="plain-list evidence-list">
            {filteredEvidence.map((evidence, idx) => (
              <li id={anchorId("evidence", evidence.evidence_id)} key={`${evidence.evidence_id}-${idx}`}>
                <p>
                  <strong>{skillDisplayLabel(evidence.skill_id, evidence.skill_name)}</strong>
                </p>
                <p className="muted">{evidence.snippet}</p>
                <EvidenceRef evidence={evidence} />
                {typeof evidence.confidence === "number" ? (
                  <p className="muted">Confidence: {Math.round(evidence.confidence * 100)}%</p>
                ) : null}
              </li>
            ))}
          </ul>
        </article>
      ) : null}
          </div>
        ) : null}

        {activeSection === "validation" ? (
          <div
            id="dashboard-section-validation"
            role="tabpanel"
            aria-labelledby="tab-validation"
            className="dashboard-section-panel"
          >
        <article className="subpanel" id="validation-issues">
          <h3>Planner Notes</h3>
          <ul className="plain-list">
            {plan.notes.map((note, idx) => (
              <li key={`${note}-${idx}`}>{note}</li>
            ))}
          </ul>

          {groupedValidation.length ? (
            <>
              <h4 className="error-title">Validation Issues</h4>
              <div className="warning-group-list">
                {groupedValidation.map((group) => {
                  const key = `${group.code}-${group.severity}`;
                  const isOpen = expandedIssueGroups[key] ?? group.severity === "error";
                  const itemsExpanded = expandedValidationItems[key] ?? false;
                  const showCount = 3;
                  const visibleItems = itemsExpanded ? group.items : group.items.slice(0, showCount);
                  const hasMore = group.items.length > showCount;
                  const why = explainWhyMatters(group.code);
                  const actions = suggestActions(group.code);
                  return (
                    <section className="warning-group" key={key}>
                      <button
                        type="button"
                        className="warning-group-header"
                        onClick={() => toggleIssueGroup(key)}
                      >
                        <span>{isOpen ? "▾" : "▸"}</span>
                        <strong>{getValidationLabel(group.code)}</strong>
                        <span className={`issue-pill ${group.severity}`}>{group.severity}</span>
                        <span className="muted">({group.items.length})</span>
                      </button>
                      {isOpen ? (
                        <div className="warning-group-body">
                          <p className="muted" style={{ fontSize: "var(--text-xs)", marginBottom: "var(--space-2)" }}>
                            Code: {group.code}
                          </p>
                          <ul className="plain-list">
                            {visibleItems.map((item, idx) => (
                              <li key={`${key}-item-${idx}`}>{item.message}</li>
                            ))}
                          </ul>
                          {hasMore && !itemsExpanded ? (
                            <button
                              type="button"
                              className="btn-muted"
                              style={{ marginTop: "var(--space-2)" }}
                              onClick={() => setExpandedValidationItems((prev) => ({ ...prev, [key]: true }))}
                            >
                              Show {group.items.length - showCount} more
                            </button>
                          ) : null}
                          <p className="muted">
                            <strong>Why it matters:</strong> {why}
                          </p>
                          <div>
                            <p className="muted">
                              <strong>What you can do:</strong>
                            </p>
                            <ul className="plain-list">
                              {actions.map((action, idx) => (
                                <li key={`${key}-action-${idx}`}>{action}</li>
                              ))}
                            </ul>
                          </div>
                        </div>
                      ) : null}
                    </section>
                  );
                })}
              </div>
            </>
          ) : null}
        </article>
          </div>
        ) : null}

        {activeSection === "advisor" ? (
          <div
            id="dashboard-section-advisor"
            role="tabpanel"
            aria-labelledby="tab-advisor"
            className="dashboard-section-panel"
          >
            <AdvisorQAPanel
              plan={plan}
              queuedQuestion={queuedAdvisorQuestion}
              queuedQuestionNonce={queuedAdvisorNonce}
              focusNonce={advisorFocusNonce}
            />
          </div>
        ) : null}
      </div>

      {/* Technical details — collapsed by default */}
      <details className="subpanel" id="technical-details" aria-label="Technical details (role ID, plan ID, debug info)">
        <summary>Technical details</summary>
        <div style={{ display: "grid", gap: "var(--space-2)", marginTop: "var(--space-3)" }}>
          <p className="muted">
            Role ID: <span className="mono">{plan.selected_role_id}</span>
          </p>
          <p className="muted">
            Plan ID: <span className="mono">{plan.plan_id}</span>
          </p>
          <p className="muted">
            Data Version: <span className="mono">{plan.data_version}</span>
          </p>
          <p className="muted">Cache Status: {plan.cache_status}</p>
          <p className="muted">
            Request ID: <span className="mono">{plan.request_id}</span>
          </p>
          {plan.readiness_summary ? (
            <div>
              <p className="muted">
                Readiness: <strong>{plan.readiness_summary.readiness_band}</strong> ({Math.round(plan.readiness_summary.score * 100)}%)
              </p>
              <p className="muted">
                Department: <strong>{plan.department_context?.primary_department || "N/A"}</strong>
                {plan.department_context?.supporting_departments?.length
                  ? ` | Supporting: ${plan.department_context.supporting_departments.join(", ")}`
                  : ""}
              </p>
              <ul className="plain-list">
                {plan.readiness_summary.factors.map((factor) => (
                  <li key={factor.name} className="muted">
                    <span className="mono">{factor.name}</span>: {Math.round(factor.value * 100)}% - {factor.description}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {plan.node_timings?.length ? (
            <div>
              <p className="muted"><strong>Node Timings</strong></p>
              <ul className="plain-list">
                {plan.node_timings.map((item, idx) => (
                  <li key={`${item.node}-${idx}`} className="muted">
                    <span className="mono">{item.node}</span> - {item.timing_ms}ms
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {plan.agent_trace?.length ? (
            <div>
              <p className="muted"><strong>Agent Trace</strong></p>
              <ol className="plain-list">
                {plan.agent_trace.map((trace, idx) => (
                  <li key={`${trace}-${idx}`} className="muted">{trace}</li>
                ))}
              </ol>
            </div>
          ) : null}
        </div>
      </details>

      {selectedCourse ? (
        <CourseQADialog
          courseId={selectedCourse.courseId}
          courseTitle={selectedCourse.courseTitle}
          planId={plan.plan_id}
          onClose={() => setSelectedCourse(null)}
        />
      ) : null}
    </section>
  );
}
