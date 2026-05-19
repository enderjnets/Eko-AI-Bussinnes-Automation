"use client";

import { useState, useMemo } from "react";
import {
  format,
  startOfMonth,
  endOfMonth,
  startOfWeek,
  endOfWeek,
  eachDayOfInterval,
  isSameMonth,
  isSameDay,
  addMonths,
  subMonths,
  isToday,
} from "date-fns";
import { es } from "date-fns/locale";
import {
  ChevronLeft,
  ChevronRight,
  CalendarDays,
  X,
  Clock,
  CheckCircle,
  Send,
  AlertTriangle,
  Pencil,
  ImageOff,
  Trash2,
  Play,
  Film,
} from "lucide-react";
import VideoModal from "./VideoModal";
import RateLimitBanner from "./RateLimitBanner";
import {
  useBufferData,
  patchBufferPost,
  type BufferPost,
} from "@/hooks/useBufferData";

const SERVICE_COLORS: Record<string, string> = {
  tiktok: "border-l-white",
  instagram: "border-l-pink-400",
  facebook: "border-l-blue-400",
};

const SERVICE_BG: Record<string, string> = {
  tiktok: "bg-white/10",
  instagram: "bg-pink-400/10",
  facebook: "bg-blue-400/10",
};

const STATUS_ICON: Record<string, React.ReactNode> = {
  sent: <CheckCircle className="w-3 h-3 text-eko-green" />,
  scheduled: <Clock className="w-3 h-3 text-yellow-400" />,
  sending: <Send className="w-3 h-3 text-eko-blue" />,
  error: <AlertTriangle className="w-3 h-3 text-red-400" />,
  draft: <Pencil className="w-3 h-3 text-gray-400" />,
};

export default function PostCalendar() {
  const { data, loading } = useBufferData();
  const [currentMonth, setCurrentMonth] = useState(new Date());
  const [selectedDay, setSelectedDay] = useState<Date | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [modalVideoUrl, setModalVideoUrl] = useState("");
  const [modalProxyUrl, setModalProxyUrl] = useState("");
  const [modalTitle, setModalTitle] = useState("");

  const monthStart = startOfMonth(currentMonth);
  const monthEnd = endOfMonth(monthStart);
  const calendarStart = startOfWeek(monthStart, { weekStartsOn: 1 });
  const calendarEnd = endOfWeek(monthEnd, { weekStartsOn: 1 });
  const days = eachDayOfInterval({ start: calendarStart, end: calendarEnd });

  const posts = data?.posts || [];

  const postsByDay = useMemo(() => {
    const map = new Map<string, BufferPost[]>();
    for (const post of posts) {
      const dateStr = post.dueAt
        ? post.dueAt.split("T")[0]
        : post.sentAt
        ? post.sentAt.split("T")[0]
        : post.createdAt.split("T")[0];
      if (!map.has(dateStr)) map.set(dateStr, []);
      map.get(dateStr)!.push(post);
    }
    return map;
  }, [posts]);

  const selectedDayPosts = selectedDay
    ? postsByDay.get(format(selectedDay, "yyyy-MM-dd")) || []
    : [];

  const weekDays = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"];

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

  const handleDelete = async (id: string) => {
    if (!confirm("¿Seguro que quieres borrar este post?")) return;
    try {
      const res = await fetch(`/content-api/posts/${id}/delete`, {
        method: "POST",
      });
      const r = await res.json();
      if (r.error) throw new Error(r.error);
      patchBufferPost(id, null);
    } catch (e: any) {
      alert("Error borrando: " + e.message);
    }
  };

  return (
    <div className="space-y-4">
      <RateLimitBanner snapshot={data} />

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <CalendarDays className="w-5 h-5 text-pink-400" />
          <h3 className="text-sm font-medium text-gray-400 capitalize">
            {format(currentMonth, "MMMM yyyy", { locale: es })}
          </h3>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setCurrentMonth(subMonths(currentMonth, 1))}
            className="p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-white/10 transition-colors"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
          <button
            onClick={() => setCurrentMonth(new Date())}
            className="px-3 py-1 rounded-lg text-xs font-medium text-gray-400 hover:text-white hover:bg-white/10 transition-colors"
          >
            Hoy
          </button>
          <button
            onClick={() => setCurrentMonth(addMonths(currentMonth, 1))}
            className="p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-white/10 transition-colors"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </div>

      {loading && posts.length === 0 && (
        <div className="flex items-center justify-center py-12">
          <div className="w-6 h-6 border-2 border-eko-blue border-t-transparent rounded-full animate-spin" />
        </div>
      )}

      {!loading && (
        <>
          <div className="grid grid-cols-7 gap-1">
            {weekDays.map((d) => (
              <div
                key={d}
                className="text-center text-xs text-gray-500 font-medium py-2"
              >
                {d}
              </div>
            ))}
          </div>

          <div className="grid grid-cols-7 gap-1">
            {days.map((day) => {
              const dateStr = format(day, "yyyy-MM-dd");
              const dayPosts = postsByDay.get(dateStr) || [];
              const isCurrentMonth = isSameMonth(day, currentMonth);
              const isTodayDate = isToday(day);
              const isSelected = selectedDay && isSameDay(day, selectedDay);

              return (
                <button
                  key={dateStr}
                  onClick={() => setSelectedDay(isSelected ? null : day)}
                  className={`relative rounded-lg border p-1.5 text-left transition-all overflow-hidden ${
                    isCurrentMonth
                      ? "bg-white/[0.02] border-white/5 hover:bg-white/[0.05]"
                      : "bg-transparent border-transparent opacity-30"
                  } ${isTodayDate ? "ring-1 ring-pink-400/50" : ""} ${
                    isSelected ? "bg-white/[0.06] border-pink-400/30" : ""
                  }`}
                  style={{ minHeight: "80px" }}
                >
                  <span
                    className={`text-xs font-medium ${
                      isTodayDate
                        ? "text-pink-400"
                        : isCurrentMonth
                        ? "text-gray-300"
                        : "text-gray-600"
                    }`}
                  >
                    {format(day, "d")}
                  </span>

                  {dayPosts.length > 0 && (
                    <div className="mt-1 space-y-1">
                      {dayPosts.slice(0, 2).map((post) => (
                        <div
                          key={post.id}
                          onClick={(e) => {
                            e.stopPropagation();
                            if (post.assets?.[0]?.source) {
                              openVideoModal(post);
                            }
                          }}
                          className={`flex items-center gap-1 rounded px-1 py-0.5 text-[9px] leading-tight truncate cursor-pointer hover:opacity-80 transition-opacity border-l-2 ${
                            SERVICE_COLORS[post.channelService] ||
                            "border-l-gray-500"
                          } ${
                            post.status === "error"
                              ? "bg-red-500/10 text-red-300"
                              : SERVICE_BG[post.channelService] ||
                                "bg-white/5 text-gray-300"
                          }`}
                          title={post.text}
                        >
                          {post.assets?.[0]?.source ? (
                            <Film className="w-2.5 h-2.5 flex-shrink-0 opacity-70" />
                          ) : (
                            <ImageOff className="w-2.5 h-2.5 flex-shrink-0 opacity-50" />
                          )}
                          <span className="truncate">
                            {post.text.slice(0, 14)}
                          </span>
                        </div>
                      ))}
                      {dayPosts.length > 2 && (
                        <div className="text-[9px] text-gray-500 px-1">
                          +{dayPosts.length - 2} más
                        </div>
                      )}
                    </div>
                  )}
                </button>
              );
            })}
          </div>
        </>
      )}

      {selectedDay && (
        <div
          className="fixed inset-0 z-40 flex items-center justify-center bg-black/60 backdrop-blur-sm"
          onClick={(e) => {
            if (e.target === e.currentTarget) setSelectedDay(null);
          }}
        >
          <div className="w-full max-w-2xl mx-4 rounded-xl border border-white/10 bg-eko-graphite shadow-2xl overflow-hidden flex flex-col max-h-[85vh]">
            <div className="flex items-center justify-between px-5 py-3 border-b border-white/5 bg-white/[0.02]">
              <h4 className="text-sm font-medium capitalize">
                {format(selectedDay, "EEEE d 'de' MMMM", { locale: es })}
              </h4>
              <div className="flex items-center gap-3">
                <span className="text-xs text-gray-500">
                  {selectedDayPosts.length} publicación
                  {selectedDayPosts.length !== 1 ? "es" : ""}
                </span>
                <button
                  onClick={() => setSelectedDay(null)}
                  className="p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-white/10 transition-colors"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>

            <div className="p-4 overflow-y-auto space-y-4">
              {selectedDayPosts.length === 0 ? (
                <p className="text-sm text-gray-500 text-center py-8">
                  Sin publicaciones este día.
                </p>
              ) : (
                selectedDayPosts.map((post) => {
                  const thumbnail = post.assets?.[0]?.thumbnail;
                  const proxyUrl = thumbnail
                    ? `/content-api/proxy-image?url=${encodeURIComponent(
                        thumbnail
                      )}`
                    : null;
                  const isError = post.status === "error";
                  const hasVideo = !!post.assets?.[0]?.source;

                  return (
                    <div
                      key={post.id}
                      className={`rounded-xl border overflow-hidden ${
                        isError
                          ? "border-red-500/15 bg-red-500/[0.03]"
                          : "border-white/5 bg-white/[0.02]"
                      }`}
                    >
                      <ModalThumbnail
                        proxyUrl={proxyUrl}
                        hasVideo={hasVideo}
                        isExpired={isError}
                        onClick={() => hasVideo && openVideoModal(post)}
                      />

                      <div className="p-3">
                        <div className="flex items-center gap-2 mb-2">
                          <span className="text-[10px] capitalize text-gray-400">
                            {post.channelService}
                          </span>
                          {STATUS_ICON[post.status] || (
                            <Clock className="w-3 h-3 text-gray-400" />
                          )}
                          {isError && (
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-red-500/10 text-red-400 border border-red-500/20">
                              Error
                            </span>
                          )}
                          {post.dueAt && post.status === "scheduled" && (
                            <span className="text-[10px] text-gray-500">
                              {new Date(post.dueAt).toLocaleTimeString(
                                "es-CO",
                                {
                                  hour: "2-digit",
                                  minute: "2-digit",
                                }
                              )}
                            </span>
                          )}
                        </div>

                        <p className="text-sm line-clamp-3">{post.text}</p>

                        <div className="flex items-center justify-end mt-3">
                          <button
                            onClick={() => handleDelete(post.id)}
                            className="p-1.5 rounded-lg text-gray-500 hover:text-red-400 hover:bg-red-500/10 transition-colors"
                            title="Borrar post"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>
      )}

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

function ModalThumbnail({
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
      className={`aspect-video bg-black/30 relative overflow-hidden ${
        hasVideo && !showPlaceholder ? "cursor-pointer group" : ""
      }`}
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
          className={`w-full h-full object-cover transition-transform duration-300 ${
            hasVideo ? "group-hover:scale-105" : ""
          }`}
          onLoad={handleLoad}
          onError={() => setImgValid(false)}
        />
      )}

      {hasVideo && !showPlaceholder && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/20 opacity-0 group-hover:opacity-100 transition-opacity">
          <div className="w-12 h-12 rounded-full bg-white/20 backdrop-blur-sm flex items-center justify-center border border-white/30">
            <Play className="w-5 h-5 text-white ml-0.5" fill="white" />
          </div>
        </div>
      )}

      {showPlaceholder && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-2">
          <ImageOff className="w-8 h-8 text-gray-600" />
          {isExpired && (
            <span className="text-[10px] text-red-400/80 font-medium">
              Media expirado
            </span>
          )}
        </div>
      )}
    </div>
  );
}
