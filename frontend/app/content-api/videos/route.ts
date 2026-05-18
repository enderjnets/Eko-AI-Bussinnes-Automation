import { NextResponse } from "next/server";

const PIPELINE_API = process.env.PIPELINE_API_URL || "http://eko-pipeline:8002";

export async function GET() {
  try {
    const r = await fetch(`${PIPELINE_API}/videos`, { cache: "no-store" });
    if (!r.ok) {
      return NextResponse.json(
        { error: `Pipeline API returned ${r.status}` },
        { status: r.status }
      );
    }
    const data = await r.json();
    return NextResponse.json(data);
  } catch (err: any) {
    return NextResponse.json(
      { error: err.message || "Failed to fetch videos" },
      { status: 500 }
    );
  }
}
