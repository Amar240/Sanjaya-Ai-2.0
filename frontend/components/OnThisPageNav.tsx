"use client";

import { useEffect, useState } from "react";

type Section = { id: string; label: string };

const SECTIONS: Section[] = [
  { id: "plan-summary", label: "Summary" },
  { id: "brain-picture", label: "Your plan in 5 steps" },
  { id: "advisor-panel", label: "Ask Advisor" },
  { id: "career-path", label: "Career path" },
  { id: "semester-roadmap", label: "Semester roadmap" },
  { id: "validation-issues", label: "Validation" },
  { id: "evidence-panel", label: "Evidence" },
];

export default function OnThisPageNav(): JSX.Element {
  const [activeId, setActiveId] = useState<string | null>(null);

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setActiveId(entry.target.id);
            break;
          }
        }
      },
      { rootMargin: "-80px 0px -60% 0px", threshold: 0 }
    );

    const elements = SECTIONS.map((s) => document.getElementById(s.id)).filter(Boolean);
    elements.forEach((el) => el && observer.observe(el));
    return () => observer.disconnect();
  }, []);

  function scrollToSection(id: string): void {
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }

  return (
    <nav
      className="on-this-page-nav"
      aria-label="On this page"
    >
      <p className="on-this-page-nav__title">On this page</p>
      <ul className="on-this-page-nav__list">
        {SECTIONS.map((section) => (
          <li key={section.id}>
            <button
              type="button"
              className={`on-this-page-nav__link ${activeId === section.id ? "on-this-page-nav__link--active" : ""}`}
              onClick={() => scrollToSection(section.id)}
            >
              {section.label}
            </button>
          </li>
        ))}
      </ul>
    </nav>
  );
}
