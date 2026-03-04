"use client";

import { formatSkillId } from "@/lib/skillLabels";
import type { PlanResponse } from "@/lib/types";

type CareerPathMapProps = {
  plan: PlanResponse;
  onAskWhyNotRole?: (roleId: string, roleTitle: string) => void;
};

function mappedSkillsForCourse(plan: PlanResponse, courseId: string): string[] {
  const card = (plan.course_purpose_cards || []).find((item) => item.course_id === courseId);
  if (!card) {
    return [];
  }
  return card.satisfied_skills;
}

export default function CareerPathMap({
  plan,
  onAskWhyNotRole,
}: CareerPathMapProps): JSX.Element {
  const alternatives = (plan.candidate_roles || []).filter(
    (item) => item.role_id !== plan.selected_role_id
  );

  return (
    <article className="subpanel career-map" id="career-path">
      <h3>Visual Career Path</h3>
      <p className="muted">
        Clear top-to-bottom path from selected role to covered skills, then semester-by-semester courses.
      </p>

      <div className="path-flow">
        <div className="path-node role-node">
          <p className="eyebrow">Target Role</p>
          <strong>{plan.selected_role_title}</strong>
          {plan.candidate_roles?.length ? (
            <div className="alt-role-block">
              <p className="eyebrow">Top Alternatives</p>
              <ul className="plain-list">
                {alternatives.length ? (
                  alternatives.map((item) => (
                    <li key={`candidate-${item.role_id}`}>
                      <p>
                        <strong>{item.role_title}</strong>
                      </p>
                      <p className="muted">Score: {item.score.toFixed(3)}</p>
                      <ul className="plain-list">
                        {item.reasons.map((reason, idx) => (
                          <li key={`${item.role_id}-reason-${idx}`} className="muted">
                            {reason}
                          </li>
                        ))}
                      </ul>
                      {onAskWhyNotRole ? (
                        <button
                          type="button"
                          className="btn-secondary"
                          onClick={() => onAskWhyNotRole(item.role_id, item.role_title)}
                        >
                          Ask: Why not this role?
                        </button>
                      ) : null}
                    </li>
                  ))
                ) : (
                  <li className="muted">No alternatives were ranked for this run.</li>
                )}
              </ul>
            </div>
          ) : null}
        </div>

        <div className="path-connector" aria-hidden />

        <div className="path-node skill-node">
          <p className="eyebrow">Required Skills</p>
          <div className="path-skill-chips">
            {plan.skill_coverage.map((skill) => (
              <span
                key={`path-skill-${skill.required_skill_id}`}
                className={skill.covered ? "chip good" : "chip bad"}
                title={
                  skill.matched_courses.length
                    ? `Mapped by ${skill.matched_courses.join(", ")}`
                    : "No mapped course yet"
                }
              >
                {formatSkillId(skill.required_skill_id)}
              </span>
            ))}
          </div>
        </div>

        <div className="path-connector" aria-hidden />

        <div className="path-semesters">
          {plan.semesters.map((semester) => (
            <div className="path-node semester-node" key={`path-sem-${semester.semester_index}`}>
              <p className="eyebrow">
                Semester {semester.semester_index} - {semester.term}
              </p>
              <p className="muted">{semester.total_credits} credits</p>
              <ul className="plain-list">
                {semester.courses.map((courseId) => {
                  const skills = mappedSkillsForCourse(plan, courseId);
                  return (
                    <li key={`path-course-${semester.semester_index}-${courseId}`}>
                      <p className="mono">{courseId}</p>
                      {skills.length ? (
                        <p className="muted">Builds: {skills.join(", ")}</p>
                      ) : (
                        <p className="muted">Support / prerequisite course</p>
                      )}
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </div>
      </div>
    </article>
  );
}
