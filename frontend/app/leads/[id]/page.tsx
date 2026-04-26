"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import {
  ArrowLeft,
  Mail,
  Phone,
  Globe,
  MapPin,
  Star,
  Sparkles,
  Send,
  Loader2,
  Calendar,
  Tag,
  AlertTriangle,
} from "lucide-react";
import Link from "next/link";
import Navbar from "@/components/Navbar";
import EmailComposer from "@/components/EmailComposer";
import { leadsApi, crmApi } from "@/lib/api";

interface Lead {
  id: number;
  business_name: string;
  category: string;
  description: string;
  email: string;
  phone: string;
  website: string;
  address: string;
  city: string;
  state: string;
  status: string;
  urgency_score: number;
  fit_score: number;
  total_score: number;
  tech_stack: string[];
  social_profiles: Record<string, string>;
  review_summary: string;
  pain_points: string[];
  trigger_events: string[];
  email_opened_count: number;
  email_clicked_count: number;
  last_contact_at: string;
  next_follow_up_at: string;
  do_not_contact: boolean;
  notes: string;
  created_at: string;
  // Extended enrichment
  website_real?: string;
  proposal_suggestion?: string;
  services?: string[];
  pricing_info?: string;
  business_hours?: string;
  about_text?: string;
  team_names?: string[];
}

export default function LeadDetailPage() {
  const params = useParams();
  const leadId = Number(params.id);
  
  const [lead, setLead] = useState<Lead | null>(null);
  const [loading, setLoading] = useState(true);
  const [showEmailComposer, setShowEmailComposer] = useState(false);
  const [transitionLoading, setTransitionLoading] = useState(false);

  useEffect(() => {
    loadLead();
  }, [leadId]);

  const loadLead = async () => {
    setLoading(true);
    try {
      const res = await leadsApi.get(leadId);
      setLead(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleTransition = async (newStatus: string) => {
    setTransitionLoading(true);
    try {
      await crmApi.transition(leadId, newStatus);
      loadLead();
    } catch (err) {
      console.error(err);
    } finally {
      setTransitionLoading(false);
    }
  };

  const getScoreColor = (score: number) => {
    if (score >= 70) return "text-eko-green";
    if (score >= 50) return "text-gold";
    if (score >= 30) return "text-orange-400";
    return "text-gray-500";
  };

  const statusColors: Record<string, string> = {
    discovered: "bg-gray-500",
    enriched: "bg-blue-500",
    scored: "bg-indigo-500",
    contacted: "bg-yellow-500",
    engaged: "bg-orange-500",
    meeting_booked: "bg-purple-500",
    proposal_sent: "bg-pink-500",
    negotiating: "bg-rose-500",
    closed_won: "bg-eko-green",
    closed_lost: "bg-red-500",
    active: "bg-emerald-500",
    at_risk: "bg-amber-500",
    churned: "bg-stone-500",
  };

  const VALID_TRANSITIONS: Record<string, string[]> = {
    discovered: ["enriched", "contacted"],
    enriched: ["scored", "contacted"],
    scored: ["contacted", "closed_lost"],
    contacted: ["engaged", "closed_lost"],
    engaged: ["meeting_booked", "proposal_sent", "closed_lost"],
    meeting_booked: ["proposal_sent", "negotiating", "closed_won", "closed_lost"],
    proposal_sent: ["negotiating", "closed_won", "closed_lost"],
    negotiating: ["closed_won", "closed_lost"],
    closed_won: ["active"],
    closed_lost: ["discovered"],
    active: ["at_risk"],
    at_risk: ["churned", "active"],
    churned: [],
  };

  const isValidTransition = (from: string, to: string) => {
    if (from === to) return false;
    return VALID_TRANSITIONS[from]?.includes(to);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-eko-graphite">
        <Navbar />
        <div className="flex items-center justify-center pt-32">
          <Loader2 className="w-8 h-8 animate-spin text-eko-blue" />
        </div>
      </div>
    );
  }

  if (!lead) {
    return (
      <div className="min-h-screen bg-eko-graphite">
        <Navbar />
        <div className="pt-32 text-center text-gray-500">Lead not found</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-eko-graphite">
      <Navbar />
      
      <main className="pt-20 pb-12 px-4 sm:px-6 lg:px-8 max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex items-center gap-4 mb-6">
          <Link
            href="/leads"
            className="flex items-center gap-1 text-sm text-gray-400 hover:text-white transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to leads
          </Link>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main info */}
          <div className="lg:col-span-2 space-y-6">
            {/* Business card */}
            <div className="rounded-xl border border-white/5 bg-white/[0.02] p-6">
              <div className="flex items-start justify-between">
                <div>
                  <h1 className="text-2xl font-bold font-display">{lead.business_name}</h1>
                  {lead.category && (
                    <span className="inline-block mt-1 text-xs px-2 py-0.5 rounded-full bg-white/5 text-gray-400">
                      {lead.category}
                    </span>
                  )}
                </div>
                <span className={`flex items-center gap-1.5 text-xs px-3 py-1 rounded-full text-white ${statusColors[lead.status] || "bg-gray-500"}`}>
                  {lead.status.replace("_", " ")}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-4 mt-4">
                {lead.email && (
                  <div className="flex items-center gap-2 text-sm text-gray-400">
                    <Mail className="w-4 h-4" />
                    {lead.email}
                  </div>
                )}
                {lead.phone && (
                  <div className="flex items-center gap-2 text-sm text-gray-400">
                    <Phone className="w-4 h-4" />
                    {lead.phone}
                  </div>
                )}
                {lead.website && (
                  <div className="flex items-center gap-2 text-sm text-gray-400">
                    <Globe className="w-4 h-4" />
                    <a href={lead.website} target="_blank" rel="noopener" className="hover:text-eko-blue truncate">
                      {lead.website}
                    </a>
                  </div>
                )}
                {lead.website_real && lead.website_real !== lead.website && (
                  <div className="flex items-center gap-2 text-sm text-gray-400">
                    <Globe className="w-4 h-4 text-eko-blue" />
                    <a href={lead.website_real} target="_blank" rel="noopener" className="hover:text-eko-blue truncate text-eko-blue">
                      Official Website
                    </a>
                  </div>
                )}
                {(lead.city || lead.state) && (
                  <div className="flex items-center gap-2 text-sm text-gray-400">
                    <MapPin className="w-4 h-4" />
                    {lead.city}, {lead.state}
                  </div>
                )}
              </div>

              {lead.description && (
                <p className="mt-4 text-sm text-gray-400">{lead.description}</p>
              )}

              {lead.do_not_contact && (
                <div className="mt-4 flex items-center gap-2 text-sm text-red-400">
                  <AlertTriangle className="w-4 h-4" />
                  Do not contact
                </div>
              )}
            </div>

            {/* Scores */}
            {lead.total_score > 0 && (
              <div className="rounded-xl border border-white/5 bg-white/[0.02] p-6">
                <h3 className="font-medium mb-4">Lead Scoring</h3>
                <div className="grid grid-cols-3 gap-4">
                  <div className="text-center">
                    <div className={`text-3xl font-bold font-display ${getScoreColor(lead.urgency_score || 0)}`}>
                      {Math.round(lead.urgency_score || 0)}
                    </div>
                    <div className="text-xs text-gray-500 mt-1">Urgency</div>
                  </div>
                  <div className="text-center">
                    <div className={`text-3xl font-bold font-display ${getScoreColor(lead.fit_score || 0)}`}>
                      {Math.round(lead.fit_score || 0)}
                    </div>
                    <div className="text-xs text-gray-500 mt-1">Fit</div>
                  </div>
                  <div className="text-center">
                    <div className={`text-3xl font-bold font-display ${getScoreColor(lead.total_score || 0)}`}>
                      {Math.round(lead.total_score || 0)}
                    </div>
                    <div className="text-xs text-gray-500 mt-1">Total</div>
                  </div>
                </div>
              </div>
            )}

            {/* Enrichment data */}
            {(lead.pain_points?.length || lead.trigger_events?.length || lead.tech_stack?.length) && (
              <div className="rounded-xl border border-white/5 bg-white/[0.02] p-6">
                <h3 className="font-medium mb-4">Research Insights</h3>
                
                {(lead.pain_points?.length ?? 0) > 0 && (
                  <div className="mb-4">
                    <h4 className="text-xs text-gray-500 uppercase tracking-wider mb-2">Pain Points</h4>
                    <div className="flex flex-wrap gap-2">
                      {(lead.pain_points || []).map((p, i) => (
                        <span key={i} className="text-xs px-2 py-1 rounded-full bg-red-500/10 text-red-400">
                          {p}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                
                {(lead.trigger_events?.length ?? 0) > 0 && (
                  <div className="mb-4">
                    <h4 className="text-xs text-gray-500 uppercase tracking-wider mb-2">Trigger Events</h4>
                    <div className="flex flex-wrap gap-2">
                      {(lead.trigger_events || []).map((t, i) => (
                        <span key={i} className="text-xs px-2 py-1 rounded-full bg-gold/10 text-gold">
                          {t}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Personalized Proposal */}
                {lead.proposal_suggestion && (
                  <div className="mb-4 p-4 rounded-lg bg-eko-blue/5 border border-eko-blue/20">
                    <h4 className="text-xs text-eko-blue uppercase tracking-wider mb-2 flex items-center gap-1">
                      <Sparkles className="w-3 h-3" />
                      AI-Generated Proposal
                    </h4>
                    <div className="text-sm text-gray-300 whitespace-pre-line leading-relaxed">
                      {lead.proposal_suggestion}
                    </div>
                  </div>
                )}

                {/* Services */}
                {(lead.services?.length ?? 0) > 0 && (
                  <div className="mb-4">
                    <h4 className="text-xs text-gray-500 uppercase tracking-wider mb-2">Services</h4>
                    <div className="flex flex-wrap gap-2">
                      {(lead.services || []).map((s, i) => (
                        <span key={i} className="text-xs px-2 py-1 rounded-full bg-purple-500/10 text-purple-400">
                          {s}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Business Hours & Pricing */}
                {(lead.business_hours || lead.pricing_info) && (
                  <div className="mb-4 grid grid-cols-2 gap-4">
                    {lead.business_hours && (
                      <div>
                        <h4 className="text-xs text-gray-500 uppercase tracking-wider mb-1">Hours</h4>
                        <p className="text-xs text-gray-400">{lead.business_hours}</p>
                      </div>
                    )}
                    {lead.pricing_info && (
                      <div>
                        <h4 className="text-xs text-gray-500 uppercase tracking-wider mb-1">Pricing</h4>
                        <p className="text-xs text-gray-400">{lead.pricing_info}</p>
                      </div>
                    )}
                  </div>
                )}

                {/* Team */}
                {(lead.team_names?.length ?? 0) > 0 && (
                  <div className="mb-4">
                    <h4 className="text-xs text-gray-500 uppercase tracking-wider mb-2">Team / Owners</h4>
                    <div className="flex flex-wrap gap-2">
                      {(lead.team_names || []).map((n, i) => (
                        <span key={i} className="text-xs px-2 py-1 rounded-full bg-white/5 text-gray-400">
                          {n}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* About */}
                {lead.about_text && (
                  <div className="mb-4">
                    <h4 className="text-xs text-gray-500 uppercase tracking-wider mb-1">About</h4>
                    <p className="text-xs text-gray-400 leading-relaxed">{lead.about_text}</p>
                  </div>
                )}

                {(lead.tech_stack?.length ?? 0) > 0 && (
                  <div>
                    <h4 className="text-xs text-gray-500 uppercase tracking-wider mb-2">Tech Stack</h4>
                    <div className="flex flex-wrap gap-2">
                      {(lead.tech_stack || []).map((t, i) => (
                        <span key={i} className="text-xs px-2 py-1 rounded-full bg-blue-500/10 text-blue-400">
                          {t}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Email Composer */}
            {showEmailComposer && (
              <EmailComposer
                leadId={lead.id}
                leadName={lead.business_name}
                leadEmail={lead.email}
                onClose={() => setShowEmailComposer(false)}
                onSent={() => { setShowEmailComposer(false); loadLead(); }}
              />
            )}
          </div>

          {/* Sidebar actions */}
          <div className="space-y-4">
            {/* Quick actions */}
            <div className="rounded-xl border border-white/5 bg-white/[0.02] p-5">
              <h3 className="font-medium mb-3">Actions</h3>
              <div className="space-y-2">
                <button
                  onClick={() => setShowEmailComposer(!showEmailComposer)}
                  disabled={!lead.email || lead.do_not_contact}
                  className="w-full flex items-center gap-2 rounded-lg bg-eko-blue px-4 py-2.5 text-sm font-medium hover:bg-eko-blue-dark disabled:opacity-50 transition-colors"
                >
                  <Send className="w-4 h-4" />
                  {showEmailComposer ? "Hide Composer" : "Send Email"}
                </button>

                {lead.status === "discovered" && (
                  <button
                    onClick={() => handleTransition("enriched")}
                    disabled={transitionLoading}
                    className="w-full flex items-center gap-2 rounded-lg bg-white/5 px-4 py-2.5 text-sm hover:bg-white/10 disabled:opacity-50 transition-colors"
                  >
                    <Sparkles className="w-4 h-4" />
                    Mark as Enriched
                  </button>
                )}

                {lead.status === "scored" && (
                  <button
                    onClick={() => handleTransition("contacted")}
                    disabled={transitionLoading}
                    className="w-full flex items-center gap-2 rounded-lg bg-white/5 px-4 py-2.5 text-sm hover:bg-white/10 disabled:opacity-50 transition-colors"
                  >
                    <Mail className="w-4 h-4" />
                    Mark as Contacted
                  </button>
                )}
              </div>
            </div>

            {/* Pipeline transitions */}
            <div className="rounded-xl border border-white/5 bg-white/[0.02] p-5">
              <h3 className="font-medium mb-3">Pipeline</h3>
              <div className="space-y-1.5">
                {[
                  { key: "discovered", label: "Discovered" },
                  { key: "enriched", label: "Enriched" },
                  { key: "scored", label: "Scored" },
                  { key: "contacted", label: "Contacted" },
                  { key: "engaged", label: "Engaged" },
                  { key: "meeting_booked", label: "Meeting Booked" },
                  { key: "proposal_sent", label: "Proposal Sent" },
                  { key: "negotiating", label: "Negotiating" },
                  { key: "closed_won", label: "Closed Won" },
                  { key: "closed_lost", label: "Closed Lost" },
                  { key: "active", label: "Active" },
                  { key: "at_risk", label: "At Risk" },
                  { key: "churned", label: "Churned" },
                ].map((stage) => {
                  const isCurrent = lead.status === stage.key;
                  const isValid = isValidTransition(lead.status, stage.key);
                  const isDisabled = transitionLoading || isCurrent || !isValid;

                  return (
                    <button
                      key={stage.key}
                      onClick={() => handleTransition(stage.key)}
                      disabled={isDisabled}
                      title={
                        isCurrent
                          ? "Etapa actual"
                          : isValid
                          ? "Mover a esta etapa"
                          : "Transición no permitida"
                      }
                      className={`w-full text-left text-sm px-3 py-2 rounded-lg transition-colors ${
                        isCurrent
                          ? "bg-eko-blue/20 text-eko-blue font-medium"
                          : isValid
                          ? "hover:bg-white/5 text-gray-400"
                          : "text-gray-600 cursor-not-allowed opacity-50"
                      }`}
                    >
                      {stage.label}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Engagement stats */}
            <div className="rounded-xl border border-white/5 bg-white/[0.02] p-5">
              <h3 className="font-medium mb-3">Engagement</h3>
              <div className="space-y-3">
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500">Emails opened</span>
                  <span className="font-medium">{lead.email_opened_count}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500">Emails clicked</span>
                  <span className="font-medium">{lead.email_clicked_count}</span>
                </div>
                {lead.last_contact_at && (
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-500">Last contact</span>
                    <span className="font-medium">
                      {new Date(lead.last_contact_at).toLocaleDateString()}
                    </span>
                  </div>
                )}
                {lead.next_follow_up_at && (
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-500">Next follow-up</span>
                    <span className="font-medium text-gold">
                      {new Date(lead.next_follow_up_at).toLocaleDateString()}
                    </span>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
