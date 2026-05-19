/**
 * Unified Buffer GraphQL client with rate-limit awareness.
 * - 5min fresh cache + 24h stale fallback
 * - Detects RATE_LIMIT_EXCEEDED and short-circuits subsequent calls
 * - Returns { data, stale, rateLimited, resetAt } so UI can render banners
 */
import { getCached, setCache } from "@/lib/api-cache";

const BUFFER_API_KEY =
  process.env.BUFFER_API_KEY || "au7VyBXcqYkOpftcaLuE7awhoSHBoXEAM-WPJWh06Fv";

const FRESH_TTL_MS = 5 * 60 * 1000;        // 5 min
const STALE_TTL_MS = 24 * 60 * 60 * 1000;  // 24h
const RATE_LIMIT_HINT_TTL_MS = 24 * 60 * 60 * 1000;

export interface BufferResult<T> {
  data: T | null;
  stale: boolean;
  rateLimited: boolean;
  rateLimitWindow?: string;
  rateLimitResetAt?: string;
  error?: string;
}

interface RateLimitHint {
  window: string;
  since: string;
  resetEstimate: string;
}

function parseWindowMs(window: string): number {
  // e.g. "24h", "1h", "60s"
  const m = window.match(/^(\d+)([smhd])$/);
  if (!m) return 24 * 60 * 60 * 1000;
  const n = parseInt(m[1], 10);
  const unit = m[2];
  return n * ({ s: 1000, m: 60_000, h: 3_600_000, d: 86_400_000 }[unit] || 1000);
}

export function getRateLimitHint(): RateLimitHint | null {
  return getCached<RateLimitHint>("buffer:rate_limit_hint");
}

function setRateLimitHint(opts: {
  window?: string;
  retryAfterSec?: number | null;
  resetAtUnix?: number | null;
}) {
  const since = new Date();
  let resetEstimate: Date;
  if (opts.retryAfterSec && opts.retryAfterSec > 0) {
    resetEstimate = new Date(since.getTime() + opts.retryAfterSec * 1000);
  } else if (opts.resetAtUnix && opts.resetAtUnix > 0) {
    resetEstimate = new Date(opts.resetAtUnix * 1000);
  } else {
    resetEstimate = new Date(since.getTime() + parseWindowMs(opts.window || "24h"));
  }
  // Hint expires when the actual reset time arrives (plus 30s safety margin).
  const hintTtlMs = Math.max(
    60_000,
    resetEstimate.getTime() - since.getTime() + 30_000
  );
  setCache<RateLimitHint>(
    "buffer:rate_limit_hint",
    {
      window: opts.window || "rolling",
      since: since.toISOString(),
      resetEstimate: resetEstimate.toISOString(),
    },
    hintTtlMs
  );
}

export function clearRateLimitHint() {
  setCache("buffer:rate_limit_hint", null as any, 1);
}

async function rawQuery<T>(query: string): Promise<T> {
  const res = await fetch("https://api.buffer.com", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${BUFFER_API_KEY}`,
    },
    body: JSON.stringify({ query }),
    cache: "no-store",
  });
  // Buffer exposes precise rate-limit info in headers.
  const retryAfterHeader = res.headers.get("retry-after"); // seconds
  const remainingHeader = res.headers.get("x-ratelimit-remaining");
  const resetHeader = res.headers.get("x-ratelimit-reset"); // unix epoch seconds
  const data = await res.json();
  if (data.errors) {
    const err: any = new Error(data.errors[0].message);
    err.code = data.errors[0]?.extensions?.code;
    err.window = data.errors[0]?.extensions?.window;
    err.retryAfterSec = retryAfterHeader ? parseInt(retryAfterHeader, 10) : null;
    err.resetAtUnix = resetHeader ? parseInt(resetHeader, 10) : null;
    err.remaining = remainingHeader ? parseInt(remainingHeader, 10) : null;
    throw err;
  }
  return data.data as T;
}

export async function bufferQuery<T>(
  query: string,
  cacheKey: string,
  ttlMs: number = FRESH_TTL_MS
): Promise<BufferResult<T>> {
  // 1. Check rate-limit hint — if set, short-circuit and serve stale only
  const hint = getRateLimitHint();
  if (hint) {
    const stale = getCached<T>(`${cacheKey}:stale`);
    return {
      data: stale,
      stale: true,
      rateLimited: true,
      rateLimitWindow: hint.window,
      rateLimitResetAt: hint.resetEstimate,
    };
  }

  // 2. Fresh cache hit
  const fresh = getCached<T>(cacheKey);
  if (fresh) {
    return { data: fresh, stale: false, rateLimited: false };
  }

  // 3. Live call
  try {
    const data = await rawQuery<T>(query);
    setCache<T>(cacheKey, data, ttlMs);
    setCache<T>(`${cacheKey}:stale`, data, STALE_TTL_MS);
    return { data, stale: false, rateLimited: false };
  } catch (err: any) {
    // Rate-limit — Buffer headers give us a precise retry-after.
    if (err.code === "RATE_LIMIT_EXCEEDED" || err.retryAfterSec) {
      setRateLimitHint({
        window: err.window || "24h",
        retryAfterSec: err.retryAfterSec,
        resetAtUnix: err.resetAtUnix,
      });
      const stale = getCached<T>(`${cacheKey}:stale`);
      const fresh = getRateLimitHint()!;
      return {
        data: stale,
        stale: true,
        rateLimited: true,
        rateLimitWindow: fresh.window,
        rateLimitResetAt: fresh.resetEstimate,
        error: err.message,
      };
    }

    // Other error — try stale
    const stale = getCached<T>(`${cacheKey}:stale`);
    if (stale) {
      return {
        data: stale,
        stale: true,
        rateLimited: false,
        error: err.message,
      };
    }
    return {
      data: null,
      stale: false,
      rateLimited: false,
      error: err.message,
    };
  }
}

let cachedOrgId: { id: string; at: number } | null = null;

export async function getOrgId(): Promise<string> {
  // Org id is essentially immutable — cache in-process for the entire container lifetime
  if (cachedOrgId && Date.now() - cachedOrgId.at < 6 * 60 * 60 * 1000) {
    return cachedOrgId.id;
  }
  const cached = getCached<string>("buffer:orgId");
  if (cached) {
    cachedOrgId = { id: cached, at: Date.now() };
    return cached;
  }

  const result = await bufferQuery<any>(
    `{ account { organizations { id } } }`,
    "buffer:orgId:raw",
    24 * 60 * 60 * 1000 // 24h
  );
  const id = result.data?.account?.organizations?.[0]?.id || "";
  if (id) {
    setCache("buffer:orgId", id, 24 * 60 * 60 * 1000);
    cachedOrgId = { id, at: Date.now() };
  }
  return id;
}
