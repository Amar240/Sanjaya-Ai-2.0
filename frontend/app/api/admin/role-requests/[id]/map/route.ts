import { NextResponse } from "next/server";

const BACKEND_URL =
  process.env.SANJAYA_BACKEND_URL ??
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  "http://127.0.0.1:8000";
const ADMIN_TOKEN = process.env.SANJAYA_ADMIN_TOKEN ?? "dev-admin-token";

type Params = { params: { id: string } };

export async function POST(request: Request, { params }: Params): Promise<NextResponse> {
  try {
    const body = await request.json().catch(() => ({}));
    const response = await fetch(
      `${BACKEND_URL}/admin/role-requests/${encodeURIComponent(params.id)}/map`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-admin-token": ADMIN_TOKEN
        },
        cache: "no-store",
        body: JSON.stringify(body)
      }
    );
    const payload = await response.json().catch(() => null);
    if (!response.ok) {
      return NextResponse.json(
        { detail: payload ?? "Unable to map role request." },
        { status: response.status }
      );
    }
    return NextResponse.json(payload, { status: 200 });
  } catch (error) {
    return NextResponse.json(
      {
        detail: `Backend connection failed at ${BACKEND_URL}. ${
          error instanceof Error ? error.message : "Unknown error"
        }`
      },
      { status: 502 }
    );
  }
}
