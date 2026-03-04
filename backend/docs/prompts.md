# Sanjaya AI — LLM Prompt Documentation and Validation

This document describes the system prompts, output schemas, and validation rules for each LLM-backed flow in the backend.

---

## 1. Chat / Intake (`chat_workflow.py`)

**Intent:** Extract structured intake fields from free-text student input.

### System prompt (summary)
- You are a university course planner intake assistant.
- Extract ONLY: program level, interests, goal type, preferred role, fusion domain, confidence level.
- Suggest from the provided role list — never invent roles or courses.
- If the student's request is ambiguous, ask one clarifying question.
- Never output PII or unrelated content.

### Output schema
```json
{
  "level": "UG" | "GR",
  "interests": ["string"],
  "goal_type": "select_role" | "type_role" | "explore",
  "preferred_role_id": "string | null",
  "requested_role_text": "string | null",
  "fusion_domain": "string | null",
  "confidence_level": "low" | "medium" | "high"
}
```

### Validation
- `level` must be `UG` or `GR`.
- `preferred_role_id` if present must exist in the loaded role catalog.
- `interests` must be a list of strings, each ≤ 100 chars.

---

## 2. Advisor (`advisor_agent.py`)

**Intent:** Answer student questions using ONLY plan context, evidence, and citations.

### System prompt (summary)
- You are an academic advisor answering based on the student's generated plan.
- Answer ONLY from plan data + evidence panel. No external knowledge.
- Provide 2–4 reasoning bullets.
- Cite ONLY IDs present in the plan (course_id, skill_id, evidence_id).
- If the question is out of scope (salary guarantees, job promises), return the safety response.

### Output schema
```json
{
  "answer": "string",
  "reasoning_points": ["string"],
  "citations": [
    {
      "label": "string",
      "citation_type": "course" | "skill" | "evidence",
      "detail": "string",
      "course_id": "string | null",
      "skill_id": "string | null",
      "evidence_id": "string | null",
      "source_url": "string | null"
    }
  ],
  "confidence": 0.0–1.0
}
```

### Validation
- `citations[].course_id` must exist in plan's semester courses.
- `citations[].skill_id` must exist in plan's skill_coverage.
- `citations[].evidence_id` must exist in plan's evidence_panel.
- If any citation references a non-existent ID, remove it from the response.

### Fallback behavior
When the LLM is unavailable or returns invalid JSON:
- The deterministic advisor logic generates a rule-based answer.
- `llm_status` is set to `"fallback"`.
- The client shows a note that the answer was generated without the LLM.

---

## 3. Storyboard (`storyboard.py`)

**Intent:** Generate a narrative career path summary in sections.

### System prompt (summary)
- Write for a first-year undergraduate audience.
- Sections should follow: "Where you're headed", "What you'll learn", "Your timeline", "Skills to build outside class".
- Each section must include citations referencing plan evidence IDs.
- Keep language encouraging, clear, and jargon-free.
- Never guarantee outcomes.

### Output schema
```json
{
  "sections": [
    {
      "title": "string",
      "body": "string",
      "citations": [{ "id": "string", "label": "string" }]
    }
  ]
}
```

### Validation
- Each section must have a non-empty `title` and `body`.
- `citations[].id` must reference an evidence, skill, or course in the plan.
- If the LLM output fails to parse or validate, fall back to the deterministic storyboard.

### Fallback behavior
- Deterministic sections are always generated first.
- The LLM optionally rewrites them if `STORYBOARD_LLM_ENABLED=true`.
- On LLM failure: `llm_status = "fallback"`, deterministic sections are returned.

---

## 4. Job Extractor (`job_extractor.py`)

**Intent:** Parse a raw job posting into structured fields.

### System prompt (summary)
- Extract ONLY: job_title, required_skills, preferred_skills, tools.
- Output valid JSON matching the schema below.
- Do NOT invent fields or interpret beyond the text.

### Output schema
```json
{
  "job_title": "string",
  "required_skills": ["string"],
  "preferred_skills": ["string"],
  "tools": ["string"]
}
```

### Validation
- `job_title` must be a non-empty string.
- All skill/tool arrays must be lists of strings.
- If LLM returns invalid JSON, the backend returns a regex-based fallback extraction.

---

## General rules

1. **No hallucinated data.** Every course, skill, and evidence ID referenced in any LLM output must exist in the loaded catalog or the current plan.
2. **Schema enforcement.** All LLM outputs are parsed through Pydantic models. Invalid output triggers fallback.
3. **Safety constraints.** Out-of-context questions (salary guarantees, job promises, personal advice) are answered with a safety response.
4. **Logging.** All LLM calls log the prompt, response, and latency. No PII is logged.
