export const copy = {
  landing: {
    eyebrow: "Sanjaya AI",
    headline: "See how your courses lead to a real job",
    support:
      "We connect your path to market-backed roles, salary ranges, and skills. No surprises when you graduate.",
    cta: "Build my roadmap",
    steps: {
      one: "Tell us a bit about you",
      two: "We match you to a role",
      three: "You get a verified roadmap",
    },
    differentiators: {
      grounded: {
        title: "Grounded in real data",
        body: "Courses from your catalog; skills and jobs from market evidence.",
      },
      prerequisite: {
        title: "Prerequisite-safe",
        body: "We check course order and credit limits so your plan is realistic.",
      },
      explainable: {
        title: "Explainable every step",
        body: "See why each course and skill matters; ask the advisor anytime.",
      },
    },
  },

  intake: {
    sectionTitle: "Build your plan",
    step1Title: "About you",
    step2Title: "Interests & role",
    step3Title: "Review & generate",
    programModeLabel: "Program level and plan mode",
    programModeQuestion: "What program level and planning mode are you using?",
    goalQuestion: "How do you want to start your goal?",
    goalSelectRole: "Pick a role",
    goalTypeRole: "Type a role title",
    goalExplore: "I\u2019m exploring",
    roleQuestion: "Which role do you want to target from market-grounded options?",
    fusionDomainQuestion:
      "Which domain passion should be combined with technology in this plan?",
    levelLabel: "Level",
    levelUG: "Undergraduate",
    levelGR: "Graduate",
    modeLabel: "Mode",
    modeCore: "Core \u2014 single career focus",
    modeFusion: "Fusion \u2014 combine two areas (e.g. Finance + CS for FinTech)",
    fusionDomainLabel: "Fusion domain",
    fusionDomainPlaceholder: "e.g. finance, biology, policy",
    fusionDomainHelper: "Which area do you want to combine with tech?",
    submitButton: "Generate my roadmap",
    submitLoading: "Building your roadmap\u2026",
    loadingRoles: "Loading role catalog from backend\u2026",
    noRoles: "No roles loaded yet. Check backend and refresh.",
    fusionRolesLoaded: (count: number) => `${count} fusion-ready roles loaded.`,
    coreRolesLoaded: (count: number) => `${count} market-grounded roles loaded.`,
    validationCredits: "Target credits must be between minimum and maximum.",
    degreeTotalCreditsLabel: "Degree total credits",
    degreeTotalCreditsHelper: "Total credits required for your degree (overall, not per semester).",
    validationDegreeTotal: "Degree total credits must be between 1 and 200.",
    nextButton: "Next",
    backButton: "Back",
    interestSuggestions: [
      "AI / Machine Learning",
      "Finance",
      "Cybersecurity",
      "Data Science",
      "Biology",
      "Policy",
      "Healthcare",
      "Operations Research",
      "Software Engineering",
    ],
    interestsLabel: "Interests",
    interestsCustomPlaceholder: "Or type your own (comma-separated)",
  },

  plan: {
    heroPath: (roleTitle: string) => `Your path to ${roleTitle}`,
    heroSupport:
      "We matched your plan to real courses and checked prerequisites. Review each step below.",
  },

  brainPicture: {
    sectionTitle: "Your plan in 5 steps",
    step1Tab: "Target Reality",
    step1Title: "What this job looks like (USA)",
    step1SalaryNote: "Salary ranges are estimates, not guarantees.",
    step1Empty:
      "We don't have job details for this role yet. You can still use the rest of your plan and ask the advisor.",
    step2Tab: "Skill Gaps",
    step2Intro: "What\u2019s covered by courses vs. what to build on your own.",
    step2Empty: "Gap report isn\u2019t available for this plan.",
    step2AllCovered: "All required skills are covered by your plan.",
    step3Tab: "Fusion Opportunities",
    step3Empty:
      "No fusion data for this plan. Choose Fusion mode and a role like FinTech to see this.",
    step3HiddenNote:
      "Fusion view is available when you choose Fusion mode and get a fusion plan.",
    step4Tab: "Career Storyboard",
    step4Title: "Your plan in plain English",
    step4Helper: "Generate a short narrative of your path. Pick tone and audience.",
    step4Button: "Generate Storyboard",
    step4Generating: "Generating\u2026",
    step4Placeholder:
      "Generate a storyboard to get a concise, cited narrative of your career path.",
    step5Tab: "Reality Check (Job Posting)",
    step5Title: "Match your plan to a real job posting",
    step5Helper:
      "Paste a job description to see how your plan lines up with required skills.",
  },

  summaryBar: {
    disclaimer:
      "Salary ranges are market estimates. Every claim is linked to a source.",
  },

  advisor: {
    title: "Advisor Q&A",
    helper:
      "Ask why this role, if the plan is realistic, or what to do about gaps. Answers use your plan and evidence.",
    placeholder: "Ask a question about your plan\u2026",
    askButton: "Ask",
    askLoading: "Thinking\u2026",
    chips: [
      "Why did you recommend this role?",
      "Is this plan feasible?",
      "What about gaps?",
      "Am I on track for this path?",
    ],
  },

  courseQA: {
    title: "Ask about this course",
    placeholder: "Ask a question about this course\u2026",
    askButton: "Ask",
    askLoading: "Thinking\u2026",
    noDescription: "Course details could not be loaded. You can still ask the advisor about this course.",
    chips: [
      "What is this course about?",
      "Why is it on my plan?",
      "What are the prerequisites?",
    ],
  },

  empty: {
    noPlanTitle: "Your roadmap will appear here",
    noPlanBody:
      "Use the form above to build your plan. We\u2019ll show your path, skills, semesters, and a reality check.",
  },

  dashboardSections: {
    path: { label: "Your path", subtitle: "See how your plan maps to the role in 5 steps." },
    semesters: { label: "Semester roadmap", subtitle: "Courses by semester and credit load." },
    courses: { label: "Course purpose", subtitle: "Why each course is on your plan." },
    skills: { label: "Skills and evidence", subtitle: "Skill coverage, career path, and evidence." },
    validation: { label: "Validation", subtitle: "Planner notes and issues to fix." },
    advisor: { label: "Advisor Q&A", subtitle: "Questions and answers about your plan." },
  } as const,

  errors: {
    generic: "Something went wrong. Please try again.",
    planFailed:
      "We couldn\u2019t build your plan. Check your choices and try again.",
    advisorFailed: "Advisor request failed. Please try again.",
  },
} as const;
