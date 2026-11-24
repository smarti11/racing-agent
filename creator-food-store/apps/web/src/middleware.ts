import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  const atHandleMatch = pathname.match(/^\/@([a-z0-9_]+)\/?$/);
  if (atHandleMatch) {
    const handle = atHandleMatch[1];
    return NextResponse.rewrite(new URL(`/creator/${handle}`, request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
