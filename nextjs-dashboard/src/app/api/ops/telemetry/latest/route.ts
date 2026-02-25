import { NextRequest, NextResponse } from "next/server";

const OPS_API_BASE_URL = process.env.OPS_API_BASE_URL || "http://nginx:80";

export async function GET(request: NextRequest) {
  const query = request.nextUrl.searchParams.toString();
  const url = `${OPS_API_BASE_URL}/api/ops/telemetry/latest${query ? `?${query}` : ""}`;

  try {
    const res = await fetch(url, { cache: "no-store" });
    const body = await res.text();
    return new NextResponse(body, {
      status: res.status,
      headers: { "content-type": res.headers.get("content-type") || "application/json" },
    });
  } catch (error) {
    return NextResponse.json(
      { error: "Failed to reach backend telemetry/latest", detail: String(error) },
      { status: 502 }
    );
  }
}
