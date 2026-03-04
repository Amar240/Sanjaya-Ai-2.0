"use client";

import { copy } from "@/lib/copy";

export type DashboardSectionKey = keyof typeof copy.dashboardSections;

const SECTION_ORDER: DashboardSectionKey[] = [
  "path",
  "semesters",
  "courses",
  "skills",
  "validation",
  "advisor",
];

type PlanDashboardNavProps = {
  activeSection: DashboardSectionKey;
  onSectionChange: (section: DashboardSectionKey) => void;
};

export default function PlanDashboardNav({
  activeSection,
  onSectionChange,
}: PlanDashboardNavProps): JSX.Element {
  return (
    <div
      className="dashboard-section-nav"
      role="tablist"
      aria-label="Plan dashboard sections"
    >
      {SECTION_ORDER.map((key) => {
        const section = copy.dashboardSections[key];
        const isSelected = activeSection === key;
        const panelId = `dashboard-section-${key}`;
        return (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={isSelected}
            aria-controls={panelId}
            id={`tab-${key}`}
            className={`dashboard-section-nav__tab ${isSelected ? "dashboard-section-nav__tab--active" : ""}`}
            onClick={() => onSectionChange(key)}
          >
            {section.label}
          </button>
        );
      })}
    </div>
  );
}

export { SECTION_ORDER };
