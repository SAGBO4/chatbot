import { NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_API_URL || process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

// The backend's /health endpoint lives outside the /api/ prefix and needs no
// credentials, so it gets its own small proxy rather than going through
// app/api/backend/[...path] (which always attaches the server-side API key).
export async function GET() {
  try {
    const res = await fetch(`${BACKEND_URL}/health`, { cache: 'no-store' });
    const text = await res.text();
    return new NextResponse(text, {
      status: res.status,
      headers: { 'Content-Type': res.headers.get('content-type') || 'application/json' },
    });
  } catch {
    return NextResponse.json({ detail: 'Could not reach the backend API.' }, { status: 502 });
  }
}
