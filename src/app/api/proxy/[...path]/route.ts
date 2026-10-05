import { NextRequest, NextResponse } from "next/server";

/**
 * API proxy: forwards all requests from the Next.js frontend to the
 * FastAPI backend. This avoids CORS issues and lets the client code
 * use relative paths without exposing the backend URL to the browser.
 *
 * Usage from client:
 *   fetch("/api/proxy/properties")
 *   fetch("/api/proxy/agent/chat", {
 *     method: "POST",
 *     headers: { "X-API-Key": apiKey },
 *     body: JSON.stringify({...}),
 *   })
 *
 * The X-API-Key header is forwarded to the backend so authenticated
 * endpoints work when REQUIRE_AUTH=true is set on the backend.
 *
 * Server-side, this becomes:
 *   http://localhost:8000/properties
 *   http://localhost:8000/agent/chat (POST)
 */

const BACKEND_URL =
  process.env.BACKEND_URL ||
  (process.env.VERCEL_URL
    ? `https://${process.env.VERCEL_URL}/api`
    : "http://localhost:8000");

/**
 * Headers that should be forwarded from the client request to the backend.
 * We do NOT forward all headers — only the ones we explicitly want to
 * pass through, to prevent header injection attacks.
 */
function buildForwardedHeaders(req: NextRequest): Headers {
  const headers = new Headers();
  headers.set("Content-Type", req.headers.get("content-type") || "application/json");

  const apiKey = req.headers.get("x-api-key") || process.env.API_KEY || process.env.NEXT_PUBLIC_API_KEY;
  if (apiKey) {
    headers.set("X-API-Key", apiKey.trim());
  }

  const auth = req.headers.get("authorization");
  if (auth) {
    headers.set("Authorization", auth);
  }

  return headers;
}

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  const url = new URL(req.url);
  const targetPath = "/" + path.join("/");
  const search = url.search || "";
  const targetUrl = `${BACKEND_URL}${targetPath}${search}`;

  try {
    const res = await fetch(targetUrl, {
      method: "GET",
      headers: buildForwardedHeaders(req),
      cache: "no-store",
    });
    const text = await res.text();
    return new NextResponse(text, {
      status: res.status,
      headers: {
        "Content-Type": res.headers.get("content-type") || "application/json",
      },
    });
  } catch (e) {
    return NextResponse.json(
      { error: "Backend unreachable", targetUrl },
      { status: 502 }
    );
  }
}

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  const targetPath = "/" + path.join("/");
  const targetUrl = `${BACKEND_URL}${targetPath}`;

  try {
    const body = await req.text();
    const res = await fetch(targetUrl, {
      method: "POST",
      headers: buildForwardedHeaders(req),
      body,
    });
    const text = await res.text();
    return new NextResponse(text, {
      status: res.status,
      headers: {
        "Content-Type": res.headers.get("content-type") || "application/json",
      },
    });
  } catch (e) {
    return NextResponse.json(
      { error: "Backend unreachable", targetUrl },
      { status: 502 }
    );
  }
}

export async function PUT(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  const targetPath = "/" + path.join("/");
  const targetUrl = `${BACKEND_URL}${targetPath}`;

  try {
    const body = await req.text();
    const res = await fetch(targetUrl, {
      method: "PUT",
      headers: buildForwardedHeaders(req),
      body,
    });
    const text = await res.text();
    return new NextResponse(text, {
      status: res.status,
      headers: {
        "Content-Type": res.headers.get("content-type") || "application/json",
      },
    });
  } catch (e) {
    return NextResponse.json(
      { error: "Backend unreachable", targetUrl },
      { status: 502 }
    );
  }
}

export async function DELETE(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  const targetPath = "/" + path.join("/");
  const targetUrl = `${BACKEND_URL}${targetPath}`;

  try {
    const res = await fetch(targetUrl, {
      method: "DELETE",
      headers: buildForwardedHeaders(req),
    });
    const text = await res.text();
    return new NextResponse(text, {
      status: res.status,
      headers: {
        "Content-Type": res.headers.get("content-type") || "application/json",
      },
    });
  } catch (e) {
    return NextResponse.json(
      { error: "Backend unreachable", targetUrl },
      { status: 502 }
    );
  }
}
