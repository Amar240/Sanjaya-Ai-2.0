import type {
  AdvisorRequest,
  AdvisorResponse,
  ChatRequest,
  ChatResponse,
  InsightsSummary,
  JobMatchRequest,
  JobMatchResponse,
  PlanRequest,
  PlanResponse,
  StoryboardRequest,
  StoryboardResponse,
  RoleRequestItem,
  RoleOption
} from "@/lib/types";

async function parseJsonOrError(response: Response): Promise<unknown> {
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const detailValue =
      payload && typeof payload === "object" && "detail" in payload
        ? (payload as { detail: unknown }).detail
        : null;
    const detailText =
      typeof detailValue === "string"
        ? detailValue
        : detailValue
          ? JSON.stringify(detailValue)
          : null;
    const detail =
      detailText
        ? detailText
        : `Request failed with status ${response.status}`;
    throw new Error(detail);
  }
  return payload;
}

export async function fetchRoles(): Promise<RoleOption[]> {
  const response = await fetch("/api/roles", {
    method: "GET",
    cache: "no-store"
  });
  const payload = await parseJsonOrError(response);
  return payload as RoleOption[];
}

export async function createPlan(input: PlanRequest): Promise<PlanResponse> {
  const response = await fetch("/api/plan", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(input)
  });
  const payload = await parseJsonOrError(response);
  return payload as PlanResponse;
}

export async function sendChat(input: ChatRequest): Promise<ChatResponse> {
  const response = await fetch("/api/chat", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(input)
  });
  const payload = await parseJsonOrError(response);
  return payload as ChatResponse;
}

export async function askAdvisor(
  input: AdvisorRequest
): Promise<AdvisorResponse> {
  const response = await fetch("/api/advisor", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(input)
  });
  const payload = await parseJsonOrError(response);
  return payload as AdvisorResponse;
}

export async function generateStoryboard(
  input: StoryboardRequest
): Promise<StoryboardResponse> {
  const response = await fetch("/api/plan/storyboard", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(input)
  });
  const payload = await parseJsonOrError(response);
  return payload as StoryboardResponse;
}

export async function matchJobPosting(input: JobMatchRequest): Promise<JobMatchResponse> {
  const response = await fetch("/api/job/match", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(input),
  });
  const payload = await parseJsonOrError(response);
  return payload as JobMatchResponse;
}

export async function fetchAdminInsights(window = "30d"): Promise<InsightsSummary> {
  const response = await fetch(`/api/admin/insights?window=${encodeURIComponent(window)}`, {
    method: "GET",
    cache: "no-store"
  });
  const payload = await parseJsonOrError(response);
  return payload as InsightsSummary;
}

export async function fetchRoleRequests(
  params: { status?: string; min_count?: number; show_all?: boolean } = {}
): Promise<RoleRequestItem[]> {
  const qs = new URLSearchParams();
  if (params.status) qs.set("status", params.status);
  if (typeof params.min_count === "number") qs.set("min_count", String(params.min_count));
  if (typeof params.show_all === "boolean") qs.set("show_all", params.show_all ? "true" : "false");
  const response = await fetch(`/api/admin/role-requests?${qs.toString()}`, {
    method: "GET",
    cache: "no-store"
  });
  const payload = await parseJsonOrError(response);
  if (payload && typeof payload === "object" && "items" in payload) {
    return (payload as { items: RoleRequestItem[] }).items;
  }
  return [];
}

export async function fetchRoleRequestById(roleRequestId: string): Promise<RoleRequestItem> {
  const response = await fetch(`/api/admin/role-requests/${encodeURIComponent(roleRequestId)}`, {
    method: "GET",
    cache: "no-store"
  });
  const payload = await parseJsonOrError(response);
  return payload as RoleRequestItem;
}

export async function ignoreRoleRequest(roleRequestId: string): Promise<RoleRequestItem> {
  const response = await fetch(
    `/api/admin/role-requests/${encodeURIComponent(roleRequestId)}/ignore`,
    { method: "POST" }
  );
  const payload = await parseJsonOrError(response);
  return payload as RoleRequestItem;
}

export async function mapRoleRequest(
  roleRequestId: string,
  mappedRoleId: string,
  note?: string
): Promise<RoleRequestItem> {
  const response = await fetch(
    `/api/admin/role-requests/${encodeURIComponent(roleRequestId)}/map`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mapped_role_id: mappedRoleId, note: note ?? null })
    }
  );
  const payload = await parseJsonOrError(response);
  return payload as RoleRequestItem;
}

export async function createRoleFromRequest(
  roleRequestId: string
): Promise<{ draft_id: string; new_role_id: string }> {
  const response = await fetch(
    `/api/admin/role-requests/${encodeURIComponent(roleRequestId)}/create-role`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({})
    }
  );
  const payload = await parseJsonOrError(response);
  return payload as { draft_id: string; new_role_id: string };
}
