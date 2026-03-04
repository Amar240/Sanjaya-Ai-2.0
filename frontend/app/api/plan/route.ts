import { NextResponse } from "next/server";

const BACKEND_URL = process.env.SANJAYA_BACKEND_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export async function POST(request: Request): Promise<NextResponse> {
  try {
    const body = await request.json();
    const response = await fetch(`${BACKEND_URL}/plan`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      cache: "no-store",
      body: JSON.stringify(body)
    });
    const payload = await response.json().catch(() => null);
    if (!response.ok) {
      return NextResponse.json(
        { detail: payload ?? "Unable to generate plan from backend." },
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
