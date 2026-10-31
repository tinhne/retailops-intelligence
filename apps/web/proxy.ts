import { NextResponse, type NextRequest } from "next/server";

const SESSION_COOKIE = "ro_session";

/**
 * Optimistic guard: visitors without a session cookie go straight to sign-in instead of
 * loading the app shell first. It is not a security boundary. The API decides every request
 * (ADR-0004), and an expired cookie is caught by the first 401.
 */
export function proxy(request: NextRequest) {
  if (request.cookies.has(SESSION_COOKIE)) return NextResponse.next();

  const url = request.nextUrl.clone();
  const next = `${request.nextUrl.pathname}${request.nextUrl.search}`;
  url.pathname = "/login";
  url.search = next === "/" ? "" : `?next=${encodeURIComponent(next)}`;
  return NextResponse.redirect(url);
}

export const config = {
  // Everything except the API, Next.js internals, static files and the public pages.
  matcher: ["/((?!api/|_next/|login|demo|favicon\\.ico|.*\\.[a-zA-Z0-9]+$).*)"],
};
