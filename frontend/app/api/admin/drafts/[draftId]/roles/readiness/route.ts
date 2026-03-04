import { NextResponse } from "next/server";

const BACKEND_URL =
  process.env.SANJAYA_BACKEND_URL ??
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  "http://127.0.0.1:8000";
const ADMIN_TOKEN = process.env.SANJAYA_ADMIN_TOKEN ?? "dev-admin-token";

type Params = { params: { draftId: string } };

export async function GET(request: Request, { params }: Params): Promise<NextResponse> {
  try {
    const url = new URL(request.url);
    const departmentOwner = url.searchParams.get("department_owner") ?? "";
    const response = await fetch(
      `${BACKEND_URL}/admin/drafts/${encodeURIComponent(params.draftId)}/roles/readiness?department_owner=${encodeURIComponent(departmentOwner)}`,
      {
        method: "GET",
        headers: { "x-admin-token": ADMIN_TOKEN },
        cache: "no-store",
      }
    );
    const payload = await response.json().catch(() => null);
    if (!response.ok) {
      return NextResponse.json(
        { detail: payload ?? "Unable to load role readiness status." },
        { status: response.status }
      );
    }
    return NextResponse.json(payload, { status: 200 });
  } catch (error) {
    return NextResponse.json(
      {
        detail: `Backend connection failed at ${BACKEND_URL}. ${
          error instanceof Error ? error.message : "Unknown error"
        }`,
      },
      { status: 502 }
    );
  }
}
