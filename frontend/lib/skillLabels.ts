/**
 * Maps skill IDs (e.g. SK_*) to human-friendly labels for student-facing UI.
 * Prefer skill_name from API when available; use this as fallback.
 */

const SKILL_LABELS: Record<string, string> = {
  SK_PROBABILITY: "Probability",
  SK_STATISTICS: "Statistics",
  SK_OPTIMIZATION: "Optimization",
  SK_RISK_ANALYTICS: "Risk analytics",
  SK_FIN_ACCOUNTING: "Financial accounting",
  SK_PYTHON: "Python",
  SK_SQL: "SQL",
  SK_DATA_ANALYSIS: "Data analysis",
  SK_MACHINE_LEARNING: "Machine learning",
  SK_NETWORK_SECURITY: "Network security",
  SK_SOFTWARE_ENGINEERING: "Software engineering",
  SK_COMMUNICATION: "Communication",
  SK_PROJECT_MANAGEMENT: "Project management",
  SK_LEADERSHIP: "Leadership",
};

/**
 * Returns a human-friendly label for a skill ID.
 * Use when API does not provide skill_name.
 */
export function formatSkillId(id: string): string {
  if (!id || typeof id !== "string") return id;
  const trimmed = id.trim();
  const known = SKILL_LABELS[trimmed];
  if (known) return known;
  // Fallback: strip SK_ prefix and title-case with spaces
  const withoutPrefix = trimmed.replace(/^SK_/i, "");
  return withoutPrefix
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(" ");
}

/**
 * Returns display label for a skill: prefers name when provided, else formatSkillId(id).
 */
export function skillDisplayLabel(skillId: string, skillName?: string | null): string {
  if (skillName && skillName.trim()) return skillName.trim();
  return formatSkillId(skillId);
}
