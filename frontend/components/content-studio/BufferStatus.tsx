"use client";

import { useState } from "react";
import {
  Loader2,
  RefreshCw,
  CheckCircle,
  Clock,
  Send,
  AlertTriangle,
  Wifi,
  WifiOff,
  BarChart3,
  ChevronDown,
  ChevronUp,
  ImageOff,
  Eye,
  EyeOff,
  Play,
} from "lucide-react";
import VideoModal from "./VideoModal";
import RateLimitBanner from "./RateLimitBanner";
import { useBufferData, type BufferPost } from "@/hooks/useBufferData";

interface ChannelStats {
  total: number;
  sent: number;
  scheduled: number;
  sending: number;
  error: number;
  draft: number;
}

const serviceColors: Record<string, string> = {
  tiktok: "text-white",
  instagram: "text-pink-400",
  facebook: "text-blue-400",
};

const STATUS_CONFIG: Record<
  string,
  { color: string; icon: any; label: string }
> = {
  sent: { color: "text-eko-green", icon: CheckCircle, label: "Publicado" },
  scheduled: { color: "text-yellow-400", icon: Clock, label: "Programado" },
  sending: { color: "text-eko-blue", icon: Send, label: "Enviando" },
  error: { color: "text-red-400", icon: AlertTriangle, label: "Error" },
  draft: { color: "text-gray-400", icon: Clock, label: "Borrador" },
};

export default function BufferStatus() {
  const { data, loading, refresh } = useBufferData();
  const [expandedChannel, setExpandedChannel] = useState<string | null>(null);
  const [showErrors, setShowErrors] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [modalVideoUrl, setModalVideoUrl] = useState("");
  const [modalProxyUrl, setModalProxyUrl] = useState("");
  const [modalTitle, setModalTitle] = useState("");

  const channels = data?.channels || [];
  const posts = data?.posts || [];

  const getStats = (channelId: string): ChannelStats => {
    const channelPosts = posts.filter((p) => p.channelId === channelId);
    return {
      total: channelPosts.length,
      sent: channelPosts.filter((p) => p.status === "sent").length,
      scheduled: channelPosts.filter((p) => p.status === "scheduled").length,
      sending: channelPosts.filter((p) => p.status === "sending").length,
      error: channelPosts.filter((p) => p.status === "error").length,
      draft: channelPosts.filter((p) => p.status === "draft").length,
    };
  };

  const totalErrors = posts.filter((p) => p.status === "error").length;

  const openVideoModal = (post: BufferPost) => {
    const source = post.assets?.[0]?.source;
    if (!source) return;
    setModalVideoUrl(source);
    setModalProxyUrl(
      `/content-api/proxy-video?url=${encodeURIComponent(source)}`
    );
    setModalTitle(
      post.text.slice(0, 60) + (post.text.length > 60 ? "..." : "")
    );
    setModalOpen(true);
  };

  if (loading && channels.length === 0) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-6 h-6 animate-spin text-eko-blue" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <RateLimitBanner snapshot={data} />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          {
            label: "Canales",
            value: channels.length,
            icon: BarChart3,
            color: "text-gray-400",
          },
          {
            label: "Posts activos",
            value: posts.filter((p) => p.status !== "error").length,
            icon: CheckCircle,
            color: "text-eko-green",
          },
          {
            label: "Programados",
            value: posts.filter((p) => p.status === "scheduled").length,
            icon: Clock,
            color: "text-yellow-400",
          },
          {
            label: "Errores",
            value: totalErrors,
            icon: AlertTriangle,
            color: "text-red-400",
          },
        ].map((s) => (
          <div
            key={s.label}
            className="rounded-xl border border-white/5 bg-white/[0.02] p-3"
          >
            <div className="flex items-center gap-2 mb-1">
              <s.icon className={`w-4 h-4 ${s.color}`} />
              <span className="text-xs text-gray-500">{s.label}</span>
            </div>
            <div className="text-xl font-bold">{s.value}</div>
          </div>
        ))}
      </div>

      <div className="flex items-center gap-2">
        <button
          onClick={() => setShowErrors(!showErrors)}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
            showErrors
              ? "bg-red-500/10 text-red-400 border border-red-500/20"
              : "bg-white/5 text-gray-400 border border-white/5 hover:bg-white/10"
          }`}
        >
          {showErrors ? (
            <Eye className="w-3.5 h-3.5" />
          ) : (
            <EyeOff className="w-3.5 h-3.5" />
          )}
          Mostrar errores ({totalErrors})
        </button>
        <button
          onClick={refresh}
          disabled={loading}
          className="ml-auto p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-white/10 transition-colors disabled:opacity-50"
          title="Refrescar"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
        </button>
      </div>

      {channels.length === 0 && !loading && (
        <div className="text-center py-12 text-gray-500 text-sm">
          {data?.rate_limited
            ? "Sin canales en caché — refresca cuando la cuota se restablezca."
            : "Sin canales configurados."}
        </div>
      )}

      <div className="space-y-2">
        {channels.map((ch) => {
          const stats = getStats(ch.id);
          const isExpanded = expandedChannel === ch.id;
          const channelPosts = posts
            .filter((p) => p.channelId === ch.id)
            .filter((p) => showErrors || p.status !== "error")
            .slice(0, 50);

          return (
            <div
              key={ch.id}
              className="rounded-xl border border-white/5 bg-white/[0.02] overflow-hidden"
            >
              <button
                onClick={() =>
                  setExpandedChannel(isExpanded ? null : ch.id)
                }
                className="w-full flex items-center justify-between p-4 hover:bg-white/[0.02] transition-colors"
              >
                <div className="flex items-center gap-3">
                  {ch.isDisconnected ? (
                    <WifiOff className="w-4 h-4 text-red-400" />
                  ) : (
                    <Wifi
                      className={`w-4 h-4 ${
                        serviceColors[ch.service] || "text-gray-400"
                      }`}
                    />
                  )}
                  <div className="text-left">
                    <div className="text-sm font-medium">{ch.name}</div>
                    <div className="text-xs text-gray-500 capitalize">
                      {ch.service}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <div className="hidden sm:flex items-center gap-2">
                    {stats.error > 0 && (
                      <span className="text-xs text-red-400">
                        {stats.error} error{stats.error > 1 ? "es" : ""}
                      </span>
                    )}
                    {stats.scheduled > 0 && (
                      <span className="text-xs text-yellow-400">
                        {stats.scheduled} prog.
                      </span>
                    )}
                    {stats.sent > 0 && (
                      <span className="text-xs text-eko-green">
                        {stats.sent} pub.
                      </span>
                    )}
                  </div>
                  {isExpanded ? (
                    <ChevronUp className="w-4 h-4 text-gray-500" />
                  ) : (
                    <ChevronDown className="w-4 h-4 text-gray-500" />
                  )}
                </div>
              </button>

              {isExpanded && (
                <div className="border-t border-white/5 p-4 space-y-2 max-h-96 overflow-y-auto">
                  {channelPosts.length === 0 ? (
                    <p className="text-sm text-gray-500">
                      Sin posts recientes.
                    </p>
                  ) : (
                    channelPosts.map((post) => {
                      const config =
                        STATUS_CONFIG[post.status] || STATUS_CONFIG.draft;
                      const StatusIcon = config.icon;
                      const thumbnail = post.assets?.[0]?.thumbnail;
                      const proxyUrl = thumbnail
                        ? `/content-api/proxy-image?url=${encodeURIComponent(
                            thumbnail
                          )}`
                        : null;
                      const hasVideo = !!post.assets?.[0]?.source;

                      return (
                        <div
                          key={post.id}
                          className={`flex gap-3 rounded-lg p-3 ${
                            post.status === "error"
                              ? "bg-red-500/5 border border-red-500/10"
                              : "bg-white/5"
                          }`}
                        >
                          <MonitorThumbnail
                            proxyUrl={proxyUrl}
                            hasVideo={hasVideo}
                            isExpired={post.status === "error"}
                            onClick={() => hasVideo && openVideoModal(post)}
                          />
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1">
                              <StatusIcon
                                className={`w-3 h-3 ${config.color}`}
                              />
                              <span className="text-[10px] text-gray-400">
                                {config.label}
                              </span>
                              {post.dueAt && (
                                <span className="text-[10px] text-gray-500">
                                  {new Date(post.dueAt).toLocaleString(
                                    "es-CO",
                                    {
                                      month: "short",
                                      day: "numeric",
                                      hour: "2-digit",
                                      minute: "2-digit",
                                    }
                                  )}
                                </span>
                              )}
                            </div>
                            <p className="text-sm line-clamp-2">{post.text}</p>
                          </div>
                        </div>
                      );
                    })
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
      <VideoModal
        videoUrl={modalVideoUrl}
        proxyUrl={modalProxyUrl}
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        title={modalTitle}
      />
    </div>
  );
}

function MonitorThumbnail({
  proxyUrl,
  hasVideo,
  isExpired,
  onClick,
}: {
  proxyUrl: string | null;
  hasVideo: boolean;
  isExpired: boolean;
  onClick: () => void;
}) {
  const [imgValid, setImgValid] = useState(true);

  const handleLoad = (e: React.SyntheticEvent<HTMLImageElement>) => {
    const img = e.currentTarget;
    if (img.naturalWidth < 2 && img.naturalHeight < 2) {
      setImgValid(false);
    }
  };

  const showPlaceholder = !proxyUrl || !imgValid;

  return (
    <div
      className={`w-12 h-12 rounded-lg overflow-hidden flex-shrink-0 relative ${
        hasVideo && !showPlaceholder ? "cursor-pointer group" : ""
      } ${showPlaceholder ? "bg-white/5" : ""}`}
      onClick={onClick}
      role={hasVideo ? "button" : undefined}
      tabIndex={hasVideo ? 0 : undefined}
      onKeyDown={
        hasVideo
          ? (e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onClick();
              }
            }
          : undefined
      }
    >
      {proxyUrl && imgValid && (
        <img
          src={proxyUrl}
          alt=""
          className="w-full h-full object-cover"
          onLoad={handleLoad}
          onError={() => setImgValid(false)}
        />
      )}
      {hasVideo && !showPlaceholder && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/30 opacity-0 group-hover:opacity-100 transition-opacity">
          <Play className="w-4 h-4 text-white" fill="white" />
        </div>
      )}
      {showPlaceholder && (
        <div className="w-full h-full flex flex-col items-center justify-center gap-0.5">
          <ImageOff className="w-4 h-4 text-gray-600" />
          {isExpired && (
            <span className="text-[7px] text-red-400/70">Expirado</span>
          )}
        </div>
      )}
    </div>
  );
}
