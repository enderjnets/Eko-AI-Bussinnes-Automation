"use client";

import { useEffect, useState, useCallback } from "react";

export interface BufferPost {
  id: string;
  text: string;
  status: string;
  dueAt?: string;
  sentAt?: string;
  createdAt: string;
  channelId: string;
  channelService: string;
  channel?: { name: string };
  assets?: { source?: string; thumbnail?: string; mimeType?: string }[];
  externalLink?: string;
  error?: { message?: string };
}

export interface BufferChannel {
  id: string;
  name: string;
  service: string;
  isDisconnected: boolean;
}

export interface BufferLimit {
  channelId: string;
  name?: string;
  service?: string;
  sent: number;
  scheduled: number;
  limit: number;
}

export interface BufferRateLimit {
  window?: string;
  reset_at?: string;
}

export interface BufferSnapshot {
  channels: BufferChannel[];
  posts: BufferPost[];
  limits: BufferLimit[];
  stale?: boolean;
  rate_limited?: boolean;
  rate_limit?: BufferRateLimit | null;
  fetched_at?: string;
  error?: string;
}

// Tiny in-module event bus so all useBufferData() instances share state.
let cached: BufferSnapshot | null = null;
let inflight: Promise<BufferSnapshot> | null = null;
const subscribers = new Set<(s: BufferSnapshot) => void>();
let lastFetchedAt = 0;

const STALE_FRONTEND_MS = 60 * 1000; // refetch at most once per minute

async function doFetch(force = false): Promise<BufferSnapshot> {
  if (!force && cached && Date.now() - lastFetchedAt < STALE_FRONTEND_MS) {
    return cached;
  }
  if (inflight && !force) return inflight;

  inflight = (async () => {
    const r = await fetch("/content-api/buffer-snapshot?limit=200", {
      cache: "no-store",
    });
    const data: BufferSnapshot = await r.json();
    cached = data;
    lastFetchedAt = Date.now();
    subscribers.forEach((cb) => cb(data));
    return data;
  })();

  try {
    return await inflight;
  } finally {
    inflight = null;
  }
}

export function useBufferData(): {
  data: BufferSnapshot | null;
  loading: boolean;
  refresh: () => Promise<void>;
} {
  const [data, setData] = useState<BufferSnapshot | null>(cached);
  const [loading, setLoading] = useState(!cached);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const s = await doFetch(true);
      setData(s);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let alive = true;
    const sub = (s: BufferSnapshot) => {
      if (alive) setData(s);
    };
    subscribers.add(sub);

    if (!cached) {
      setLoading(true);
      doFetch()
        .then((s) => {
          if (alive) {
            setData(s);
            setLoading(false);
          }
        })
        .catch(() => {
          if (alive) setLoading(false);
        });
    } else {
      setData(cached);
      setLoading(false);
    }

    return () => {
      alive = false;
      subscribers.delete(sub);
    };
  }, []);

  return { data, loading, refresh };
}

// Optimistic helpers (used after edit/delete to mutate cache locally)
export function patchBufferPost(
  postId: string,
  patch: Partial<BufferPost> | null
) {
  if (!cached) return;
  if (patch === null) {
    cached = {
      ...cached,
      posts: cached.posts.filter((p) => p.id !== postId),
    };
  } else {
    cached = {
      ...cached,
      posts: cached.posts.map((p) =>
        p.id === postId ? { ...p, ...patch } : p
      ),
    };
  }
  subscribers.forEach((cb) => cb(cached!));
}
