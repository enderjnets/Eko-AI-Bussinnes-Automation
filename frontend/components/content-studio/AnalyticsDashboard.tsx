"use client";

import { useEffect, useState, useMemo } from "react";
import {
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
  Legend,
} from "recharts";
import { format, subDays, parseISO } from "date-fns";
import {
  Loader2,
  Film,
  CheckCircle,
  Clock,
  TrendingUp,
} from "lucide-react";
import RateLimitBanner from "./RateLimitBanner";
import { useBufferData } from "@/hooks/useBufferData";

interface PipelineStats {
  total_pipelines: number;
  total_videos: number;
  total_duration_seconds: number;
  total_size_mb: number;
  published_videos: number;
  total_briefs: number;
  by_platform: Record<string, number>;
}

const PLATFORM_COLORS: Record<string, string> = {
  tiktok: "#ffffff",
  instagram: "#f472b6",
  facebook: "#60a5fa",
};

const STATUS_COLORS: Record<string, string> = {
  sent: "#4ade80",
  scheduled: "#facc15",
  sending: "#60a5fa",
  error: "#f87171",
  draft: "#9ca3af",
  needs_approval: "#c084fc",
};

export default function AnalyticsDashboard() {
  const { data, loading: bufferLoading } = useBufferData();
  const [pipelineStats, setPipelineStats] = useState<PipelineStats | null>(
    null
  );
  const [statsLoading, setStatsLoading] = useState(true);

  useEffect(() => {
    fetch("/content-api/stats")
      .then((r) => r.json())
      .then((d) => {
        setPipelineStats(d.error ? null : d);
        setStatsLoading(false);
      })
      .catch(() => setStatsLoading(false));
  }, []);

  const posts = data?.posts || [];
  const limits = data?.limits || [];

  const totalPosts = posts.length;
  const sentPosts = posts.filter((p) => p.status === "sent").length;
  const scheduledPosts = posts.filter((p) => p.status === "scheduled").length;
  const errorPosts = posts.filter((p) => p.status === "error").length;
  const successRate =
    sentPosts + errorPosts > 0
      ? Math.round((sentPosts / (sentPosts + errorPosts)) * 100)
      : 0;

  const platformData = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const post of posts) {
      const svc = post.channelService || "unknown";
      counts[svc] = (counts[svc] || 0) + 1;
    }
    return Object.entries(counts).map(([name, value]) => ({
      name,
      value,
      color: PLATFORM_COLORS[name] || "#9ca3af",
    }));
  }, [posts]);

  const statusData = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const post of posts) {
      counts[post.status] = (counts[post.status] || 0) + 1;
    }
    return Object.entries(counts).map(([name, value]) => ({
      name,
      value,
      color: STATUS_COLORS[name] || "#9ca3af",
    }));
  }, [posts]);

  const timelineData = useMemo(() => {
    const days: {
      date: string;
      total: number;
      tiktok: number;
      instagram: number;
      facebook: number;
    }[] = [];
    const now = new Date();
    for (let i = 29; i >= 0; i--) {
      const d = subDays(now, i);
      days.push({
        date: format(d, "dd/MM"),
        total: 0,
        tiktok: 0,
        instagram: 0,
        facebook: 0,
      });
    }
    const byDay = new Map(days.map((d, i) => [d.date, i]));

    for (const post of posts) {
      const postDate = post.sentAt
        ? parseISO(post.sentAt)
        : post.dueAt
        ? parseISO(post.dueAt)
        : parseISO(post.createdAt);
      const key = format(postDate, "dd/MM");
      const idx = byDay.get(key);
      if (idx === undefined) continue;
      days[idx].total++;
      const svc = post.channelService;
      if (svc === "tiktok") days[idx].tiktok++;
      else if (svc === "instagram") days[idx].instagram++;
      else if (svc === "facebook") days[idx].facebook++;
    }
    return days;
  }, [posts]);

  const loading = bufferLoading && statsLoading && posts.length === 0;

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-6 h-6 animate-spin text-eko-blue" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <RateLimitBanner snapshot={data} />

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <KPICard
          label="Total posts"
          value={totalPosts}
          icon={Film}
          color="text-eko-blue"
        />
        <KPICard
          label="Publicados"
          value={sentPosts}
          icon={CheckCircle}
          color="text-eko-green"
        />
        <KPICard
          label="Programados"
          value={scheduledPosts}
          icon={Clock}
          color="text-yellow-400"
        />
        <KPICard
          label="Tasa éxito"
          value={`${successRate}%`}
          icon={TrendingUp}
          color="text-pink-400"
        />
      </div>

      {pipelineStats && (
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-4">
          <KPICard
            label="Videos producidos"
            value={pipelineStats.total_videos}
            icon={Film}
            color="text-purple-400"
          />
          <KPICard
            label="Duración total"
            value={`${Math.floor(pipelineStats.total_duration_seconds / 60)}m`}
            icon={Clock}
            color="text-eko-green"
          />
          <KPICard
            label="Publicados"
            value={pipelineStats.published_videos}
            icon={CheckCircle}
            color="text-emerald-400"
          />
          <KPICard
            label="Briefs"
            value={pipelineStats.total_briefs}
            icon={TrendingUp}
            color="text-yellow-300"
          />
          <KPICard
            label="Pipelines"
            value={pipelineStats.total_pipelines}
            icon={Film}
            color="text-eko-blue"
          />
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="rounded-xl border border-white/5 bg-white/[0.02] p-4">
          <h4 className="text-sm font-medium text-gray-400 mb-4">
            Posts por plataforma
          </h4>
          <div className="h-64">
            {platformData.length === 0 ? (
              <div className="h-full flex items-center justify-center text-xs text-gray-500">
                Sin datos
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={platformData}
                    cx="50%"
                    cy="50%"
                    innerRadius={50}
                    outerRadius={80}
                    paddingAngle={4}
                    dataKey="value"
                    stroke="none"
                  >
                    {platformData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#1a1a1a",
                      border: "1px solid rgba(255,255,255,0.1)",
                      borderRadius: "8px",
                      color: "#fff",
                      fontSize: "12px",
                    }}
                    formatter={(value: any) => [`${value} posts`, "Cantidad"]}
                  />
                  <Legend
                    formatter={(value: string) => (
                      <span className="text-gray-400 capitalize">{value}</span>
                    )}
                  />
                </PieChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        <div className="rounded-xl border border-white/5 bg-white/[0.02] p-4">
          <h4 className="text-sm font-medium text-gray-400 mb-4">
            Posts por estado
          </h4>
          <div className="h-64">
            {statusData.length === 0 ? (
              <div className="h-full flex items-center justify-center text-xs text-gray-500">
                Sin datos
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={statusData}>
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="rgba(255,255,255,0.05)"
                  />
                  <XAxis
                    dataKey="name"
                    tick={{ fill: "#9ca3af", fontSize: 11 }}
                    axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
                    tickFormatter={(v: string) =>
                      ({
                        sent: "Pub",
                        scheduled: "Prog",
                        sending: "Env",
                        error: "Err",
                        draft: "Borr",
                        needs_approval: "Pend",
                      }[v] || v)
                    }
                  />
                  <YAxis
                    tick={{ fill: "#9ca3af", fontSize: 11 }}
                    axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
                    allowDecimals={false}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#1a1a1a",
                      border: "1px solid rgba(255,255,255,0.1)",
                      borderRadius: "8px",
                      color: "#fff",
                      fontSize: "12px",
                    }}
                    formatter={(value: any) => [`${value}`, "Posts"]}
                  />
                  <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                    {statusData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-white/5 bg-white/[0.02] p-4">
        <h4 className="text-sm font-medium text-gray-400 mb-4">
          Actividad últimos 30 días
        </h4>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={timelineData}>
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="rgba(255,255,255,0.05)"
              />
              <XAxis
                dataKey="date"
                tick={{ fill: "#9ca3af", fontSize: 10 }}
                axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
                interval="preserveStartEnd"
              />
              <YAxis
                tick={{ fill: "#9ca3af", fontSize: 11 }}
                axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
                allowDecimals={false}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#1a1a1a",
                  border: "1px solid rgba(255,255,255,0.1)",
                  borderRadius: "8px",
                  color: "#fff",
                  fontSize: "12px",
                }}
              />
              <Legend
                formatter={(value: string) => (
                  <span className="text-gray-400 capitalize">{value}</span>
                )}
              />
              <Line
                type="monotone"
                dataKey="tiktok"
                stroke={PLATFORM_COLORS.tiktok}
                strokeWidth={2}
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="instagram"
                stroke={PLATFORM_COLORS.instagram}
                strokeWidth={2}
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="facebook"
                stroke={PLATFORM_COLORS.facebook}
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {limits.length > 0 && (
        <div className="rounded-xl border border-white/5 bg-white/[0.02] p-4">
          <h4 className="text-sm font-medium text-gray-400 mb-4">
            Límites diarios por canal
          </h4>
          <div className="space-y-3">
            {limits.map((l) => {
              const used = l.sent + l.scheduled;
              const pct = l.limit > 0 ? (used / l.limit) * 100 : 0;
              const color =
                pct >= 90
                  ? "bg-red-500"
                  : pct >= 60
                  ? "bg-yellow-400"
                  : "bg-eko-green";

              return (
                <div key={l.channelId}>
                  <div className="flex items-center justify-between text-sm mb-1">
                    <span className="capitalize text-gray-300">
                      {l.service} — {l.name}
                    </span>
                    <span className="text-gray-500 text-xs">
                      {used} / {l.limit} ({Math.round(pct)}%)
                    </span>
                  </div>
                  <div className="h-2 rounded-full bg-white/5 overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all ${color}`}
                      style={{ width: `${Math.min(pct, 100)}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

function KPICard({
  label,
  value,
  icon: Icon,
  color,
}: {
  label: string;
  value: string | number;
  icon: React.ElementType;
  color: string;
}) {
  return (
    <div className="rounded-xl border border-white/5 bg-white/[0.02] p-4">
      <div className={`${color} mb-2`}>
        <Icon className="w-5 h-5" />
      </div>
      <p className="text-2xl font-bold">{value}</p>
      <p className="text-xs text-gray-500 mt-1">{label}</p>
    </div>
  );
}
