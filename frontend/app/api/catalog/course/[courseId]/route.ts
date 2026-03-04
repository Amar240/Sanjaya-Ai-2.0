import { NextResponse } from "next/server";

const BACKEND_URL =
  process.env.SANJAYA_BACKEND_URL ??
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  "http://127.0.0.1:8000";

type Params = { params: { courseId: string } };

export async function GET(
  _request: Request,
  { params }: Params
): Promise<NextResponse> {
  try {
    const { courseId } = params;
    const response = await fetch(
      `${BACKEND_URL}/catalog/course/${encodeURIComponent(courseId)}`,
      { method: "GET", cache: "no-store" }
    );
    const payload = await response.json().catch(() => null);
    if (!response.ok) {
      return NextResponse.json(
        { detail: payload?.detail ?? "Course not found." },
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
