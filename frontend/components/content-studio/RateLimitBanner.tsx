"use client";

import { AlertTriangle, Clock } from "lucide-react";
import { useEffect, useState } from "react";
import type { BufferSnapshot } from "@/hooks/useBufferData";

function formatCountdown(resetAt?: string): string {
  if (!resetAt) return "—";
  const diffMs = new Date(resetAt).getTime() - Date.now();
  if (diffMs <= 0) return "ya disponible";
  const h = Math.floor(diffMs / 3_600_000);
  const m = Math.floor((diffMs % 3_600_000) / 60_000);
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

export default function RateLimitBanner({
  snapshot,
}: {
  snapshot: BufferSnapshot | null;
}) {
  const [, tick] = useState(0);

  useEffect(() => {
    if (!snapshot?.rate_limited) return;
    const i = setInterval(() => tick((n) => n + 1), 30_000);
    return () => clearInterval(i);
  }, [snapshot?.rate_limited]);

  if (!snapshot) return null;
  if (!snapshot.rate_limited && !snapshot.stale && !snapshot.error) return null;

  if (snapshot.rate_limited) {
    return (
      <div className="rounded-xl border border-yellow-500/30 bg-yellow-500/5 p-3 flex items-start gap-3">
        <AlertTriangle className="w-4 h-4 text-yellow-400 mt-0.5 flex-shrink-0" />
        <div className="flex-1 text-xs">
          <p className="text-yellow-200 font-medium mb-0.5">
            Buffer API rate-limited
          </p>
          <p className="text-yellow-200/70">
            Mostrando datos cacheados. La cuota se restablece en{" "}
            <Clock className="w-3 h-3 inline mb-0.5" />{" "}
            <strong>{formatCountdown(snapshot.rate_limit?.reset_at)}</strong>
            {snapshot.rate_limit?.window
              ? ` (ventana: ${snapshot.rate_limit.window})`
              : ""}
            .
          </p>
        </div>
      </div>
    );
  }

  if (snapshot.stale) {
    return (
      <div className="rounded-xl border border-blue-500/20 bg-blue-500/5 p-3 flex items-start gap-3">
        <Clock className="w-4 h-4 text-blue-400 mt-0.5 flex-shrink-0" />
        <div className="flex-1 text-xs text-blue-200/80">
          Mostrando datos cacheados de Buffer.
        </div>
      </div>
    );
  }

  if (snapshot.error) {
    return (
      <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-3 flex items-start gap-3">
        <AlertTriangle className="w-4 h-4 text-red-400 mt-0.5 flex-shrink-0" />
        <div className="flex-1 text-xs text-red-300">
          Error contactando Buffer: {snapshot.error}
        </div>
      </div>
    );
  }

  return null;
}
