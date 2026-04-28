"use client";

import { useState, useEffect, useCallback } from "react";
import { Loader2, TrendingUp, Mail, Eye, MousePointer, MessageCircle, Calendar, DollarSign, Target } from "lucide-react";
import Navbar from "@/components/Navbar";
import { analyticsApi, campaignsApi } from "@/lib/api";

interface Campaign {
  id: number;
  name: string;
  status: string;
  leads_total: number;
  leads_contacted: number;
  leads_responded: number;
  leads_converted: number;
}

interface CampaignAnalytics {
  campaign_id: number;
  campaign_name: string;
  funnel: {
    leads: number;
    emails_sent: number;
    emails_opened: number;
    emails_clicked: number;
    replies: number;
    meetings_booked: number;
    closed_won: number;
  };
  rates: {
    open_rate: number;
    click_rate: number;
    reply_rate: number;
    meeting_rate: number;
    conversion_rate: number;
  };
}

export default function AnalyticsPage() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [selectedCampaign, setSelectedCampaign] = useState<number | null>(null);
  const [campaignAnalytics, setCampaignAnalytics] = useState<CampaignAnalytics | null>(null);
  const [pipeline, setPipeline] = useState<any>(null);
  const [performance, setPerformance] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [campRes, pipeRes, perfRes] = await Promise.all([
        campaignsApi.list(),
        analyticsApi.pipeline(),
        analyticsApi.performance(),
      ]);
      setCampaigns(campRes.data || []);
      setPipeline(pipeRes.data);
      setPerformance(perfRes.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const loadCampaignAnalytics = useCallback(async (campaignId: number) => {
    try {
      const res = await analyticsApi.campaign(campaignId);
      setCampaignAnalytics(res.data);
    } catch (err) {
      console.error(err);
    }
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen bg-eko-graphite">
        <Navbar />
        <main className="pt-20 pb-12 px-4 flex items-center justify-center">
          <Loader2 className="w-6 h-6 animate-spin text-eko-blue" />
        </main>
      </div>
    );
  }

  const funnelStages = campaignAnalytics ? [
    { label: "Leads", value: campaignAnalytics.funnel.leads, icon: <Target className="w-4 h-4" />, color: "text-gray-400" },
    { label: "Emails enviados", value: campaignAnalytics.funnel.emails_sent, icon: <Mail className="w-4 h-4" />, color: "text-eko-blue" },
    { label: "Abiertos", value: campaignAnalytics.funnel.emails_opened, icon: <Eye className="w-4 h-4" />, color: "text-eko-green" },
    { label: "Clicks", value: campaignAnalytics.funnel.emails_clicked, icon: <MousePointer className="w-4 h-4" />, color: "text-gold" },
    { label: "Respuestas", value: campaignAnalytics.funnel.replies, icon: <MessageCircle className="w-4 h-4" />, color: "text-purple-400" },
    { label: "Reuniones", value: campaignAnalytics.funnel.meetings_booked, icon: <Calendar className="w-4 h-4" />, color: "text-pink-400" },
    { label: "Cerrados", value: campaignAnalytics.funnel.closed_won, icon: <DollarSign className="w-4 h-4" />, color: "text-eko-green" },
  ] : [];

  return (
    <div className="min-h-screen bg-eko-graphite">
      <Navbar />
      <main className="pt-20 pb-12 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto">
        <div className="mb-6">
          <h1 className="text-2xl font-bold font-display">Analytics</h1>
          <p className="text-gray-400 text-sm">Métricas de pipeline y campañas</p>
        </div>

        {/* Pipeline Overview */}
        {pipeline && (
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3 mb-8">
            {Object.entries(pipeline.pipeline || {}).map(([status, count]: [string, any]) => (
              <div key={status} className="rounded-xl border border-white/5 bg-white/[0.02] p-3 text-center">
                <div className="text-lg font-bold font-display">{count as number}</div>
                <div className="text-xs text-gray-500 capitalize mt-1">{status.replace("_", " ")}</div>
              </div>
            ))}
          </div>
        )}

        {/* Performance Cards */}
        {performance && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
            <div className="rounded-xl border border-white/5 bg-white/[0.02] p-4">
              <div className="text-xs text-gray-500 mb-1">Total Leads</div>
              <div className="text-2xl font-bold font-display">{performance.total_leads}</div>
            </div>
            <div className="rounded-xl border border-white/5 bg-white/[0.02] p-4">
              <div className="text-xs text-gray-500 mb-1">Contactados</div>
              <div className="text-2xl font-bold font-display text-eko-blue">{performance.contacted}</div>
            </div>
            <div className="rounded-xl border border-white/5 bg-white/[0.02] p-4">
              <div className="text-xs text-gray-500 mb-1">Cerrados</div>
              <div className="text-2xl font-bold font-display text-eko-green">{performance.closed_won}</div>
            </div>
            <div className="rounded-xl border border-white/5 bg-white/[0.02] p-4">
              <div className="text-xs text-gray-500 mb-1">Conversión</div>
              <div className="text-2xl font-bold font-display text-gold">{performance.conversion_rate}%</div>
            </div>
          </div>
        )}

        {/* Campaign Selector */}
        <div className="mb-6">
          <h2 className="text-lg font-medium mb-3">Analytics por campaña</h2>
          <div className="flex flex-wrap gap-2">
            {campaigns.map((camp) => (
              <button
                key={camp.id}
                onClick={() => {
                  setSelectedCampaign(camp.id);
                  loadCampaignAnalytics(camp.id);
                }}
                className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                  selectedCampaign === camp.id
                    ? "bg-eko-blue text-white"
                    : "bg-white/5 text-gray-400 hover:bg-white/10"
                }`}
              >
                {camp.name}
              </button>
            ))}
            {campaigns.length === 0 && (
              <p className="text-sm text-gray-500">No hay campañas activas.</p>
            )}
          </div>
        </div>

        {/* Campaign Funnel */}
        {campaignAnalytics && (
          <div className="rounded-xl border border-white/5 bg-white/[0.02] p-6">
            <h3 className="text-sm font-medium mb-4">{campaignAnalytics.campaign_name} — Funnel</h3>
            
            <div className="space-y-3 mb-6">
              {funnelStages.map((stage, idx) => {
                const prevValue = idx > 0 ? funnelStages[idx - 1].value : stage.value;
                const dropOff = prevValue > 0 ? Math.round((1 - stage.value / prevValue) * 100) : 0;
                return (
                  <div key={stage.label} className="flex items-center gap-3">
                    <div className={`w-8 h-8 rounded-lg bg-white/5 flex items-center justify-center ${stage.color}`}>
                      {stage.icon}
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs text-gray-400">{stage.label}</span>
                        <span className={`text-xs font-medium ${stage.color}`}>{stage.value}</span>
                      </div>
                      <div className="w-full bg-white/5 rounded-full h-2 overflow-hidden">
                        <div
                          className="h-full rounded-full bg-eko-blue transition-all"
                          style={{
                            width: `${campaignAnalytics.funnel.leads > 0 ? (stage.value / campaignAnalytics.funnel.leads) * 100 : 0}%`,
                            opacity: 0.3 + (idx / funnelStages.length) * 0.7,
                          }}
                        />
                      </div>
                    </div>
                    {idx > 0 && dropOff > 0 && (
                      <span className="text-xs text-red-400">-{dropOff}%</span>
                    )}
                  </div>
                );
              })}
            </div>

            {/* Rates */}
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 pt-4 border-t border-white/5">
              <div className="text-center">
                <div className="text-lg font-bold font-display text-eko-green">{campaignAnalytics.rates.open_rate}%</div>
                <div className="text-xs text-gray-500">Open rate</div>
              </div>
              <div className="text-center">
                <div className="text-lg font-bold font-display text-gold">{campaignAnalytics.rates.click_rate}%</div>
                <div className="text-xs text-gray-500">Click rate</div>
              </div>
              <div className="text-center">
                <div className="text-lg font-bold font-display text-purple-400">{campaignAnalytics.rates.reply_rate}%</div>
                <div className="text-xs text-gray-500">Reply rate</div>
              </div>
              <div className="text-center">
                <div className="text-lg font-bold font-display text-pink-400">{campaignAnalytics.rates.meeting_rate}%</div>
                <div className="text-xs text-gray-500">Meeting rate</div>
              </div>
              <div className="text-center">
                <div className="text-lg font-bold font-display text-eko-blue">{campaignAnalytics.rates.conversion_rate}%</div>
                <div className="text-xs text-gray-500">Conversion</div>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
