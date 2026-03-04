import { NextResponse } from "next/server";

const BACKEND_URL = process.env.SANJAYA_BACKEND_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export async function GET(): Promise<NextResponse> {
  try {
    const response = await fetch(`${BACKEND_URL}/roles`, {
      method: "GET",
      cache: "no-store"
    });
    const payload = await response.json().catch(() => null);
    if (!response.ok) {
      return NextResponse.json(
        { detail: payload ?? "Unable to load roles from backend." },
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
