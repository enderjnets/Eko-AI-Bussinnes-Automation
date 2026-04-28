"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import {
  Users,
  MailOpen,
  TrendingUp,
  Target,
  Zap,
  BarChart3,
  GitBranch,
  Briefcase,
  Inbox,
  ListOrdered,
  Mail,
  Calendar,
  Settings,
  FileText,
  Mic,
  ArrowRight,
  Loader2,
} from "lucide-react";
import Navbar from "@/components/Navbar";
import StatCard from "@/components/StatCard";
import PipelineBoard from "@/components/PipelineBoard";
import DiscoveryForm from "@/components/DiscoveryForm";
import RecentLeads from "@/components/RecentLeads";
import { analyticsApi, emailsApi, dealsApi } from "@/lib/api";
import VersionBadge from "@/components/VersionBadge";

const MODULES = [
  { href: "/leads", label: "Leads", subtitle: "Gestión de prospectos", icon: Users, color: "text-eko-blue bg-eko-blue/10 border-eko-blue/20" },
  { href: "/pipeline", label: "Pipeline", subtitle: "Kanban de ventas", icon: GitBranch, color: "text-eko-green bg-eko-green/10 border-eko-green/20" },
  { href: "/deals", label: "Deals", subtitle: "Oportunidades", icon: Briefcase, color: "text-gold bg-gold/10 border-gold/20" },
  { href: "/proposals", label: "Propuestas", subtitle: "AI proposals", icon: FileText, color: "text-indigo-400 bg-indigo-500/10 border-indigo-500/20" },
  { href: "/voice-agent", label: "Voice", subtitle: "VAPI calls", icon: Mic, color: "text-cyan-400 bg-cyan-500/10 border-cyan-500/20" },
  { href: "/inbox", label: "Inbox", subtitle: "Replies de leads", icon: Inbox, color: "text-rose bg-rose/10 border-rose/20", badgeKey: "unread" as const },
  { href: "/sequences", label: "Secuencias", subtitle: "Automatización", icon: ListOrdered, color: "text-purple-400 bg-purple-500/10 border-purple-500/20" },
  { href: "/campaigns", label: "Campañas", subtitle: "Email outreach", icon: Mail, color: "text-cyan-400 bg-cyan-500/10 border-cyan-500/20" },
  { href: "/calendar", label: "Calendar", subtitle: "Reuniones", icon: Calendar, color: "text-orange-400 bg-orange-500/10 border-orange-500/20" },
  { href: "/analytics", label: "Analytics", subtitle: "Métricas", icon: BarChart3, color: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20" },
  { href: "/settings", label: "Config", subtitle: "API keys y prefs", icon: Settings, color: "text-gray-300 bg-gray-500/10 border-gray-500/20" },
];

export default function Dashboard() {
  const [stats, setStats] = useState({
    total_leads: 0,
    contacted: 0,
    closed_won: 0,
    conversion_rate: 0,
    avg_lead_score: 0,
  });
  const [discoveryResult, setDiscoveryResult] = useState<any>(null);
  const [refreshLeads, setRefreshLeads] = useState(0);
  const [unreadCount, setUnreadCount] = useState(0);
  const [dealsForecast, setDealsForecast] = useState<any>(null);
  const [loadingModules, setLoadingModules] = useState(true);

  useEffect(() => {
    loadStats();
    loadUnread();
    loadForecast();
  }, []);

  const loadStats = async () => {
    try {
      const res = await analyticsApi.performance();
      setStats(res.data);
    } catch (err) {
      console.error("Failed to load stats:", err);
    }
  };

  const loadUnread = async () => {
    try {
      const res = await emailsApi.inbox({ status: "unread", limit: 1 });
      setUnreadCount(res.data?.unread_count || 0);
    } catch {
      // silently fail
    } finally {
      setLoadingModules(false);
    }
  };

  const loadForecast = async () => {
    try {
      const res = await dealsApi.forecast();
      setDealsForecast(res.data);
    } catch {
      // silently fail
    }
  };

  return (
    <div className="min-h-screen bg-eko-graphite">
      <Navbar />

      <main className="pt-20 pb-12 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold font-display">Dashboard</h1>
          <p className="text-gray-400 text-sm mt-1">
            Sistema de Agentes Autónomos para Prospección y Ventas
          </p>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <StatCard
            title="Total Leads"
            value={stats.total_leads}
            subtitle="Leads en el sistema"
            icon={Users}
            color="blue"
          />
          <StatCard
            title="Contactados"
            value={stats.contacted}
            subtitle="Leads con contacto iniciado"
            icon={MailOpen}
            color="gold"
          />
          <StatCard
            title="Conversion Rate"
            value={`${stats.conversion_rate}%`}
            subtitle="Lead → Cliente"
            icon={TrendingUp}
            color="green"
          />
          <StatCard
            title="Avg Score"
            value={Math.round(stats.avg_lead_score)}
            subtitle="Puntuación promedio"
            icon={Target}
            color="rose"
          />
        </div>

        {/* Quick Access Modules */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider">Módulos</h2>
            {dealsForecast && dealsForecast.total_weighted_value > 0 && (
              <span className="text-xs text-gray-500">
                Forecast: ${dealsForecast.total_weighted_value.toLocaleString("en-US")}
              </span>
            )}
          </div>
          {loadingModules ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-6 h-6 animate-spin text-eko-blue" />
            </div>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 2xl:grid-cols-11 gap-3">
              {MODULES.map((mod) => {
                const badge = mod.badgeKey === "unread" ? unreadCount : undefined;
                return (
                  <Link
                    key={mod.href}
                    href={mod.href}
                    className="group relative flex flex-col items-center gap-2 rounded-xl border border-white/5 bg-white/[0.02] p-4 hover:bg-white/5 hover:border-white/10 transition-all"
                  >
                    <div className={`p-2.5 rounded-lg ${mod.color}`}>
                      <mod.icon className="w-5 h-5" />
                    </div>
                    <div className="text-center">
                      <p className="text-sm font-medium group-hover:text-white transition-colors">
                        {mod.label}
                      </p>
                      <p className="text-[10px] text-gray-500 mt-0.5">{mod.subtitle}</p>
                    </div>
                    {badge !== undefined && badge > 0 && (
                      <span className="absolute top-2 right-2 flex items-center justify-center min-w-[18px] h-[18px] px-1 rounded-full bg-red-500 text-white text-[10px] font-bold">
                        {badge > 99 ? "99+" : badge}
                      </span>
                    )}
                    <ArrowRight className="w-3.5 h-3.5 text-gray-600 group-hover:text-gray-400 transition-colors mt-1" />
                  </Link>
                );
              })}
            </div>
          )}
        </div>

        {/* Pipeline */}
        <div className="mb-8">
          <PipelineBoard />
        </div>

        {/* Discovery + Recent Leads */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-1">
            <DiscoveryForm
              onSuccess={(data) => {
                setDiscoveryResult(data);
                loadStats();
                setRefreshLeads((prev) => prev + 1);
              }}
            />

            {discoveryResult && (
              <div className="mt-4 rounded-xl border border-eko-green/20 bg-eko-green/5 p-4">
                <div className="flex items-center gap-2 text-eko-green">
                  <Zap className="w-4 h-4" />
                  <span className="text-sm font-medium">
                    {discoveryResult.total} leads descubiertos
                  </span>
                </div>
              </div>
            )}
          </div>

          <div className="lg:col-span-2">
            <RecentLeads refreshTrigger={refreshLeads} />
          </div>
        </div>
      </main>

      <VersionBadge />
    </div>
  );
}
