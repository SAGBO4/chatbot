import { NextRequest, NextResponse } from 'next/server';
import { verifyTelegramInitData } from '@/lib/server/telegramAuth';

// Server-only: never prefixed with NEXT_PUBLIC_, so it is never bundled into
// client JavaScript. This is what actually fixes the "shared API key shipped
// to every visitor's browser" finding - the browser now only ever talks to
// this same-origin proxy, and only this server process holds the real key.
const BACKEND_URL = process.env.BACKEND_API_URL || process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';
const BACKEND_API_KEY = process.env.BACKEND_API_KEY || '';
// Must be the same bot as backend's TELEGRAM_BOT_TOKEN - it is what proves a
// WebApp.initData string was actually signed by Telegram for this bot.
const TELEGRAM_BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN || '';

const isProduction = process.env.NODE_ENV === 'production';

function forbidden(message: string): NextResponse {
  return NextResponse.json({ detail: message }, { status: 403 });
}

async function checkIsAdmin(userId: number): Promise<boolean> {
  try {
    const res = await fetch(`${BACKEND_URL}/api/admin/whitelist/${userId}/check`, {
      headers: BACKEND_API_KEY ? { 'X-API-Key': BACKEND_API_KEY } : {},
      cache: 'no-store',
    });
    if (!res.ok) return false;
    const data = await res.json();
    return Boolean(data?.is_whitelisted);
  } catch {
    return false;
  }
}

async function proxy(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
): Promise<NextResponse> {
  const { path } = await context.params;
  const [seg0, seg1, seg2, seg3] = path;

  // Cryptographically verify who is actually calling (see telegramAuth.ts).
  // initDataUnsafe-style client claims are never trusted here.
  const verified = verifyTelegramInitData(request.headers.get('x-telegram-init-data'), TELEGRAM_BOT_TOKEN);
  const verifiedUserId = verified?.user.id ?? null;

  // Local `next dev` only, and only when no real Telegram session is
  // present at all - lets the Mini App still be exercised outside of
  // Telegram during development (see the ?user_id=/?admin=1 dev shortcuts
  // in TelegramContext.tsx), while every real deployment (`next build` +
  // `next start` always sets NODE_ENV=production) enforces real
  // verification with no bypass.
  const devFallback = !isProduction && verifiedUserId === null;

  const verifiedIsAdmin = verifiedUserId !== null ? await checkIsAdmin(verifiedUserId) : false;
  const requireVerifiedAdmin = () => verifiedIsAdmin || devFallback;

  // ---- Authorization gate: admin-only surfaces ----
  if (seg0 === 'admin') {
    const isWhitelistSelfCheck = seg1 === 'whitelist' && seg2 !== undefined && seg3 === 'check';
    const isSelfCheck = isWhitelistSelfCheck && verifiedUserId !== null && verifiedUserId === Number(seg2);
    if (!isSelfCheck && !requireVerifiedAdmin()) {
      return forbidden('Telegram admin authentication required.');
    }
  } else if (seg0 === 'knowledge' && seg1 === 'ingest') {
    if (!requireVerifiedAdmin()) return forbidden('Telegram admin authentication required.');
  } else if (seg0 === 'moderation' && seg1 === 'warnings') {
    if (!requireVerifiedAdmin()) return forbidden('Telegram admin authentication required.');
  } else if (seg0 === 'tickets' && (seg1 === 'by-support-message' || seg2 === 'resolve' || seg2 === 'support-card')) {
    // Agent-only actions: resolving a ticket, or the bot-internal
    // message-id lookup/card-attachment endpoints (never called from this
    // frontend, but gated here too in case that ever changes).
    if (!requireVerifiedAdmin()) return forbidden('Telegram admin authentication required.');
  }

  const targetUrl = new URL(`${BACKEND_URL}/api/${path.join('/')}`);
  request.nextUrl.searchParams.forEach((value, key) => {
    targetUrl.searchParams.append(key, value);
  });

  let bodyText: string | undefined;
  if (request.method !== 'GET' && request.method !== 'HEAD') {
    bodyText = await request.text();
  }

  // ---- IDOR guard: a non-admin caller can only ever see/create their own
  // tickets. The verified id always wins over anything the client sent. ----
  if (seg0 === 'tickets') {
    const isTicketsRead = (path.length === 1 || path.length === 2) && request.method === 'GET';
    const isCreateTicket = path.length === 1 && request.method === 'POST';

    if (isTicketsRead && !verifiedIsAdmin) {
      if (verifiedUserId !== null) {
        targetUrl.searchParams.set('user_id', String(verifiedUserId));
      } else if (!devFallback) {
        return forbidden('Telegram authentication required to view tickets.');
      }
    }

    if (isCreateTicket) {
      if (verifiedUserId !== null && bodyText) {
        try {
          const payload = JSON.parse(bodyText);
          payload.user_id = verifiedUserId;
          bodyText = JSON.stringify(payload);
        } catch {
          // Malformed JSON - let the backend's own schema validation reject it.
        }
      } else if (verifiedUserId === null && !devFallback) {
        return forbidden('Telegram authentication required to create a ticket.');
      }
    }

    const isAttachment = path.length === 3 && seg2 === 'attachment' && request.method === 'POST';
    if (isAttachment && verifiedUserId === null && !devFallback) {
      return forbidden('Telegram authentication required to attach a screenshot.');
    }
  }

  const headers = new Headers();
  headers.set('Content-Type', request.headers.get('content-type') || 'application/json');
  headers.set('Accept', 'application/json');
  if (BACKEND_API_KEY) {
    headers.set('X-API-Key', BACKEND_API_KEY);
  }

  const init: RequestInit = {
    method: request.method,
    headers,
    cache: 'no-store',
  };
  if (bodyText) {
    init.body = bodyText;
  }

  let backendResponse: Response;
  try {
    backendResponse = await fetch(targetUrl.toString(), init);
  } catch {
    return NextResponse.json(
      { detail: 'Could not reach the backend API.' },
      { status: 502 }
    );
  }

  const responseText = await backendResponse.text();
  return new NextResponse(responseText, {
    status: backendResponse.status,
    headers: {
      'Content-Type': backendResponse.headers.get('content-type') || 'application/json',
    },
  });
}

export { proxy as GET, proxy as POST, proxy as PUT, proxy as DELETE, proxy as PATCH };
