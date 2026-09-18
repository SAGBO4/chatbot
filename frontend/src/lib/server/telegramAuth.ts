import { createHmac, timingSafeEqual } from 'crypto';

// A Telegram Mini App's WebApp.initData is a signed, URL-encoded query
// string (auth_date, user, hash, ...). window.Telegram.WebApp.initDataUnsafe
// is exactly that - unsafe: it is parsed client-side with no signature
// check, so anything reading it (including our own frontend) must never
// trust it for authorization. This verifies the raw initData string
// server-side per Telegram's documented algorithm:
// https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
export interface VerifiedTelegramUser {
  id: number;
  first_name?: string;
  last_name?: string;
  username?: string;
  language_code?: string;
}

export interface VerifiedInitData {
  user: VerifiedTelegramUser;
  authDate: number;
}

// Telegram's own recommendation: reject stale initData so a leaked/logged
// string can't be replayed indefinitely to impersonate a user.
const MAX_INIT_DATA_AGE_SECONDS = 24 * 60 * 60;

export function verifyTelegramInitData(
  initData: string | null | undefined,
  botToken: string | null | undefined
): VerifiedInitData | null {
  if (!initData || !botToken) return null;

  let params: URLSearchParams;
  try {
    params = new URLSearchParams(initData);
  } catch {
    return null;
  }

  const hash = params.get('hash');
  // Buffer.from(str, 'hex') silently truncates at the first invalid
  // character instead of rejecting the string, so "<64 valid hex
  // chars><garbage>" would parse to the exact same 32-byte buffer as the
  // valid hash alone and slip past timingSafeEqual below. Reject anything
  // that isn't exactly 64 lowercase hex characters up front.
  if (!hash || !/^[0-9a-f]{64}$/.test(hash)) return null;
  params.delete('hash');

  const dataCheckString = Array.from(params.entries())
    .sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))
    .map(([key, value]) => `${key}=${value}`)
    .join('\n');

  const secretKey = createHmac('sha256', 'WebAppData').update(botToken).digest();
  const computedHash = createHmac('sha256', secretKey).update(dataCheckString).digest('hex');

  const computedBuf = Buffer.from(computedHash, 'hex');
  const givenBuf = Buffer.from(hash, 'hex');
  if (computedBuf.length !== givenBuf.length || !timingSafeEqual(computedBuf, givenBuf)) {
    return null;
  }

  const authDateRaw = params.get('auth_date');
  const authDate = authDateRaw ? parseInt(authDateRaw, 10) : NaN;
  if (!authDate || Date.now() / 1000 - authDate > MAX_INIT_DATA_AGE_SECONDS) {
    return null;
  }

  const userRaw = params.get('user');
  if (!userRaw) return null;

  try {
    const parsed = JSON.parse(userRaw);
    if (typeof parsed?.id !== 'number') return null;
    return { user: parsed as VerifiedTelegramUser, authDate };
  } catch {
    return null;
  }
}
