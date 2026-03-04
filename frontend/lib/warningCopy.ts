/** Friendly labels for validation codes (student-facing). */
export const VALIDATION_LABELS: Record<string, string> = {
  OFFERING_MISMATCH: "Course may not be offered in this term",
  COREQ_NOT_SATISFIED: "Corequisite not in same term",
  ANTIREQ_CONFLICT: "Overlapping course conflict",
  CREDITS_BELOW_MIN: "Credits below minimum",
  CREDIT_OVER_MAX: "Too many credits",
  PREREQ_ORDER: "Prerequisite order",
  ROLE_REQUEST_UNRESOLVED: "Role match unclear",
  ROLE_REALITY_MISSING: "Job profile not available",
  EVIDENCE_INTEGRITY_VIOLATION: "Evidence alignment issue",
  TOTAL_CREDITS_OVER_DEGREE: "Plan exceeds degree total credits",
  TOTAL_CREDITS_UNDER_DEGREE: "Plan below degree total credits",
};

export function getValidationLabel(code: string): string {
  return VALIDATION_LABELS[code] ?? code.replace(/_/g, " ").toLowerCase();
}

const WHY_BY_CODE: Record<string, string> = {
  OFFERING_MISMATCH:
    "The course is currently placed in a term where catalog offerings may not match.",
  COREQ_NOT_SATISFIED:
    "Corequisite timing is not aligned, which can block enrollment approval.",
  ANTIREQ_CONFLICT:
    "Antirequisite courses overlap in content, and taking both may not count.",
  CREDITS_BELOW_MIN:
    "Low credits can affect pace, financial aid rules, or full-time status.",
  CREDIT_OVER_MAX:
    "Credit load exceeds preferred cap and may reduce schedule feasibility.",
  PREREQ_ORDER:
    "Prerequisite order is not fully satisfied before a dependent course.",
  ROLE_REQUEST_UNRESOLVED:
    "Requested role text did not map confidently to a curated role.",
  ROLE_REALITY_MISSING:
    "USA role reality data is not attached for the selected role.",
  EVIDENCE_INTEGRITY_VIOLATION:
    "Some evidence references do not align cleanly with the plan context.",
  TOTAL_CREDITS_OVER_DEGREE:
    "Your plan has more credits than your degree allows; excess credits may not count toward graduation.",
  TOTAL_CREDITS_UNDER_DEGREE:
    "Your plan is below the typical degree requirement; you may need more courses to graduate.",
};

const ACTIONS_BY_CODE: Record<string, string[]> = {
  OFFERING_MISMATCH: [
    "Enable optional terms and regenerate the plan.",
    "Swap the course with an equivalent offered in the target term.",
  ],
  COREQ_NOT_SATISFIED: [
    "Move the corequisite into the same semester.",
    "If unavailable, replace with an approved alternative pair.",
  ],
  ANTIREQ_CONFLICT: [
    "Keep only one course from the antirequisite pair.",
    "Confirm credit policy before enrolling in both.",
  ],
  CREDITS_BELOW_MIN: [
    "Add a low-risk elective to reach minimum credits.",
    "Confirm reduced-load policy if you intentionally stay below minimum.",
  ],
  CREDIT_OVER_MAX: [
    "Move one course to a later term or optional term.",
    "Reduce target credits and regenerate.",
  ],
  PREREQ_ORDER: [
    "Move prerequisite courses earlier in the roadmap.",
    "Enable optional terms for more scheduling flexibility.",
  ],
  ROLE_REQUEST_UNRESOLVED: [
    "Pick one of the ranked candidate roles now.",
    "Use a clearer role title and regenerate.",
  ],
  ROLE_REALITY_MISSING: [
    "Use evidence panel + market sources for role grounding.",
    "Ask advisor/admin to add a role reality profile for this role.",
  ],
  EVIDENCE_INTEGRITY_VIOLATION: [
    "Use citations linked to current evidence panel items.",
    "Regenerate to refresh evidence alignment.",
  ],
  TOTAL_CREDITS_OVER_DEGREE: [
    "Reduce courses or semesters so total credits do not exceed your degree total.",
    "Increase degree total in Build your plan if your program allows a higher cap.",
  ],
  TOTAL_CREDITS_UNDER_DEGREE: [
    "Add more courses or enable optional terms to reach your degree total.",
    "Confirm with your program if a lower total is acceptable.",
  ],
};

export function explainWhyMatters(code: string): string {
  return WHY_BY_CODE[code] ?? "This issue can affect plan reliability or execution quality.";
}

export function suggestActions(code: string): string[] {
  return (
    ACTIONS_BY_CODE[code] ?? [
      "Review the affected courses/skills and regenerate.",
      "Ask advisor for a constrained fix grounded in current plan context.",
    ]
  );
}
