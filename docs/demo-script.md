# Sanjaya AI — 3-Minute Demo Script

## Demo Seed

Use this exact configuration to guarantee a deterministic demo with fusion data:

| Field | Value |
|-------|-------|
| Level | UG (Undergraduate) |
| Mode | Fusion |
| Fusion Domain | finance |
| Goal Type | Pick a role |
| Preferred Role | Quant Risk Analyst or FinTech Engineer |
| Current Semester | 1 |
| Start Term | Fall |
| Interests | operations research, analytics, optimization |

This seed ensures `fusion_summary` and `fusion_pack_summary` are returned, so all 5 Brain Picture steps are populated.

---

## Script (3 minutes)

### 0:00–0:20 — Open with the problem

> "Every year, thousands of freshmen walk into college without knowing how their courses connect to a real job. They pick classes, hope for the best, and are shocked when they graduate and the job market expects skills they never built. Sanjaya AI changes that."

**Action:** Show the landing page. Point to the headline and the 3-step visual.

### 0:20–0:40 — Show intake

> "A student tells us their level, interests, and whether they want to combine two areas. Let me show you Fusion Mode — say a student loves finance but is also studying computer science."

**Action:** Select UG, Fusion mode, type `finance` as the fusion domain, pick a fusion-ready role (e.g. Quant Risk Analyst). Click "Generate my roadmap".

### 0:40–1:10 — Brain Picture overview

> "Here's what makes Sanjaya different. Instead of a generic course list, we give them a 5-step Brain Picture."

**Action:** Scroll to the plan. Point to "Your path to Quant Risk Analyst" hero line.

- **Step 1 (Target Reality):** "This is what the job actually looks like in the US: tasks, salary, and cited sources."
- **Step 2 (Skill Gaps):** "Here are the skills covered by their courses vs. what's missing. Green means covered, red means they need to build it themselves."

### 1:10–1:40 — Fusion and Storyboard

- **Step 3 (Fusion Opportunities):** "Because they chose Fusion, we show the Finance + CS overlap: a curated pack with domain readiness, tech readiness, and starter projects."
- **Step 4 (Career Storyboard):** Click "Generate Storyboard". "Now the plan becomes a readable narrative — sections, citations, tailored to a first-year audience."

### 1:40–2:10 — Reality Check and Advisor

- **Step 5 (Reality Check):** Click "Load Preset 1" or paste a job posting. Click "Extract & Match". "We compare their roadmap to a real job posting — covered skills, missing skills, and project recommendations."
- **Advisor:** "And any time the student has a question, they can ask the advisor. It answers with reasoning and citations from the plan."

**Action:** Click a suggested chip like "Why this role?" and show the answer.

### 2:10–2:40 — How it works

> "Under the hood: we use LLMs plus RAG over the UD course catalog and market evidence. Every recommendation is grounded — no hallucinated courses, no made-up skills. The advisor only answers from plan context."

**Action:** Scroll down to the "Technical details" (click to expand briefly). Show plan ID, cache status.

### 2:40–3:00 — Adoption pitch

> "This is designed to plug into any university portal. We built it so that a school like UD could add it as a tile in their student dashboard — pre-fill from their student information system and give every student a verified, personalized roadmap. Thank you."

**Action:** Return to the landing page or show the 3-step visual one more time.

---

## Tips

- Keep the backend running before the demo. Hit `/health` to verify.
- Use the demo seed above to ensure consistent results.
- If the LLM is slow, the storyboard and advisor have deterministic fallbacks.
- Practice the 3-minute timing. The script above is tight; skip Step 5 details if running long.
