"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Loader2,
  RefreshCw,
  Play,
  Film,
  Smartphone,
  Monitor,
  Clock,
  HardDrive,
  Sparkles,
  AlertTriangle,
} from "lucide-react";
import VideoModal from "./VideoModal";

interface Video {
  id: string;
  type: "short" | "long";
  filename: string;
  size_mb: number;
  created_at: string;
  url: string;
  thumbnail_url: string | null;
  title?: string | null;
  duration?: number | null;
  business_name?: string | null;
}

const PUBLIC_BASE = "https://ender-rog.tail25dc73.ts.net";

function formatDuration(seconds?: number | null): string {
  if (!seconds || seconds <= 0) return "—";
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  if (m === 0) return `${s}s`;
  return `${m}m ${s.toString().padStart(2, "0")}s`;
}

function timeAgo(iso: string): string {
  try {
    const then = new Date(iso).getTime();
    const diff = Date.now() - then;
    const sec = Math.floor(diff / 1000);
    if (sec < 60) return "hace segundos";
    const min = Math.floor(sec / 60);
    if (min < 60) return `hace ${min} min`;
    const hr = Math.floor(min / 60);
    if (hr < 24) return `hace ${hr}h`;
    const day = Math.floor(hr / 24);
    if (day < 30) return `hace ${day}d`;
    return new Date(iso).toLocaleDateString("es-CO", {
      month: "short",
      day: "numeric",
    });
  } catch {
    return "—";
  }
}

export default function VideosList() {
  const [videos, setVideos] = useState<Video[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState<"all" | "short" | "long">("all");
  const [modalOpen, setModalOpen] = useState(false);
  const [modalVideo, setModalVideo] = useState<Video | null>(null);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const r = await fetch("/content-api/videos", { cache: "no-store" });
      const data = await r.json();
      if (data.error) throw new Error(data.error);
      setVideos(data.videos || []);
    } catch (e: any) {
      setError(e.message || "Error cargando videos");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const filtered = useMemo(
    () =>
      filter === "all"
        ? videos
        : videos.filter((v) => v.type === filter),
    [videos, filter]
  );

  const counts = useMemo(
    () => ({
      all: videos.length,
      short: videos.filter((v) => v.type === "short").length,
      long: videos.filter((v) => v.type === "long").length,
    }),
    [videos]
  );

  const openVideo = (v: Video) => {
    setModalVideo(v);
    setModalOpen(true);
  };

  const videoUrl = (v: Video) => `${PUBLIC_BASE}${v.url}`;
  const thumbUrl = (v: Video) =>
    v.thumbnail_url ? `${PUBLIC_BASE}${v.thumbnail_url}` : null;

  return (
    <div className="space-y-4">
      {/* Header / filters */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-pink-400" />
          <h3 className="text-sm font-medium text-gray-300">
            Videos generados por el pipeline
          </h3>
          <span className="text-xs text-gray-500">
            ({videos.length} {videos.length === 1 ? "video" : "videos"})
          </span>
        </div>
        <div className="flex items-center gap-2">
          {(["all", "short", "long"] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                filter === f
                  ? "bg-pink-500/20 text-pink-400 border border-pink-500/30"
                  : "bg-white/5 text-gray-400 border border-white/5 hover:bg-white/10"
              }`}
            >
              {f === "all" ? "Todos" : f === "short" ? "Shorts" : "Longs"}
              <span className="ml-1.5 text-[10px] opacity-70">
                {counts[f]}
              </span>
            </button>
          ))}
          <button
            onClick={load}
            disabled={loading}
            className="p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-white/10 transition-colors disabled:opacity-50"
            title="Refrescar"
          >
            <RefreshCw
              className={`w-4 h-4 ${loading ? "animate-spin" : ""}`}
            />
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-4 text-red-400 text-sm flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 flex-shrink-0" />
          {error}
        </div>
      )}

      {loading && videos.length === 0 && (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="w-6 h-6 animate-spin text-pink-400" />
        </div>
      )}

      {!loading && filtered.length === 0 && !error && (
        <div className="text-center py-16 text-gray-500">
          <Film className="w-10 h-10 mx-auto mb-3 opacity-30" />
          <p className="text-sm">
            {filter === "all"
              ? "Aún no hay videos generados. Ejecuta el pipeline para crear contenido."
              : `No hay videos del tipo "${filter}".`}
          </p>
        </div>
      )}

      {/* Grid */}
      {filtered.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((v) => {
            const TypeIcon = v.type === "short" ? Smartphone : Monitor;
            const isShort = v.type === "short";
            return (
              <div
                key={v.id}
                className="rounded-xl border border-white/5 bg-white/[0.02] overflow-hidden hover:border-white/10 transition-colors group"
              >
                {/* Thumbnail / Video preview */}
                <div
                  className={`relative bg-black/40 cursor-pointer overflow-hidden ${
                    isShort ? "aspect-[9/16] max-h-64" : "aspect-video"
                  }`}
                  onClick={() => openVideo(v)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      openVideo(v);
                    }
                  }}
                >
                  {thumbUrl(v) ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={thumbUrl(v)!}
                      alt={v.title || v.id}
                      className="w-full h-full object-cover"
                      loading="lazy"
                      onError={(e) => {
                        (e.currentTarget as HTMLImageElement).style.display =
                          "none";
                      }}
                    />
                  ) : (
                    <video
                      src={videoUrl(v)}
                      className="w-full h-full object-cover"
                      preload="metadata"
                      muted
                      playsInline
                    />
                  )}
                  {/* Type badge */}
                  <div
                    className={`absolute top-2 left-2 flex items-center gap-1 px-2 py-1 rounded-md text-[10px] font-medium backdrop-blur-sm ${
                      isShort
                        ? "bg-pink-500/30 text-pink-100 border border-pink-400/30"
                        : "bg-blue-500/30 text-blue-100 border border-blue-400/30"
                    }`}
                  >
                    <TypeIcon className="w-3 h-3" />
                    {isShort ? "Short" : "Long"}
                  </div>
                  {/* Play overlay */}
                  <div className="absolute inset-0 flex items-center justify-center bg-black/30 opacity-0 group-hover:opacity-100 transition-opacity">
                    <div className="w-14 h-14 rounded-full bg-white/20 backdrop-blur-sm flex items-center justify-center border border-white/40">
                      <Play
                        className="w-6 h-6 text-white ml-1"
                        fill="white"
                      />
                    </div>
                  </div>
                </div>

                {/* Info */}
                <div className="p-3">
                  <p className="text-sm font-medium text-gray-200 line-clamp-2 mb-1">
                    {v.title || v.filename}
                  </p>
                  {v.business_name && (
                    <p className="text-[11px] text-pink-400/80 mb-2">
                      {v.business_name}
                    </p>
                  )}
                  <div className="flex items-center gap-3 text-[10px] text-gray-500">
                    <span className="flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {formatDuration(v.duration)}
                    </span>
                    <span className="flex items-center gap-1">
                      <HardDrive className="w-3 h-3" />
                      {v.size_mb} MB
                    </span>
                    <span className="ml-auto">{timeAgo(v.created_at)}</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Modal */}
      {modalVideo && (
        <VideoModal
          videoUrl={videoUrl(modalVideo)}
          isOpen={modalOpen}
          onClose={() => setModalOpen(false)}
          title={
            modalVideo.title ||
            modalVideo.business_name ||
            modalVideo.filename
          }
        />
      )}
    </div>
  );
}
