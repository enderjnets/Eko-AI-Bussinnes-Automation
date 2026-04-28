"use client";

import { useCallback, memo, useState } from "react";
import { ArrowRight, ArrowLeft, Send, Loader2, RefreshCw, AlertCircle } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { crmApi } from "@/lib/api";
import { useColumnLeads } from "@/hooks/useColumnLeads";

const PIPELINE_STAGES = [
  { key: "discovered", label: "Descubiertos", color: "bg-gray-500" },
  { key: "enriched", label: "Enriquecidos", color: "bg-blue-500" },
  { key: "scored", label: "Scoring", color: "bg-indigo-500" },
  { key: "contacted", label: "Contactados", color: "bg-yellow-500" },
  { key: "engaged", label: "Engaged", color: "bg-orange-500" },
  { key: "meeting_booked", label: "Citas", color: "bg-purple-500" },
  { key: "proposal_sent", label: "Propuestas", color: "bg-pink-500" },
  { key: "negotiating", label: "Negociando", color: "bg-rose-500" },
  { key: "closed_won", label: "Ganados", color: "bg-eko-green" },
  { key: "closed_lost", label: "Perdidos", color: "bg-red-500" },
  { key: "active", label: "Activos", color: "bg-emerald-500" },
  { key: "at_risk", label: "En Riesgo", color: "bg-amber-500" },
  { key: "churned", label: "Churned", color: "bg-stone-500" },
];

// Valid transitions mirroring backend VALID_TRANSITIONS
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

interface Lead {
  id: number;
  business_name: string;
  category: string;
  city: string;
  total_score: number;
  status: string;
  email?: string;
  phone?: string;
}

const getScoreColor = (score: number) => {
  if (score >= 70) return "text-eko-green";
  if (score >= 50) return "text-gold";
  if (score >= 30) return "text-orange-400";
  return "text-gray-500";
};

const getValidNextStages = (status: string): string[] => {
  return VALID_TRANSITIONS[status] || [];
};

const getValidPrevStages = (status: string): string[] => {
  const prev: string[] = [];
  for (const [from, toList] of Object.entries(VALID_TRANSITIONS)) {
    if (toList.includes(status)) {
      prev.push(from);
    }
  }
  return prev;
};

// ------------------------------------------------------------------
// Single Lead Card (memoized)
// ------------------------------------------------------------------

interface LeadCardProps {
  lead: Lead;
  isLoading: boolean;
  onTransition: (lead: Lead, newStatus: string) => void;
  onSendEmail: (lead: Lead) => void;
}

const LeadCard = memo(function LeadCard({
  lead,
  isLoading,
  onTransition,
  onSendEmail,
}: LeadCardProps) {
  const validNext = getValidNextStages(lead.status);
  const validPrev = getValidPrevStages(lead.status);

  return (
    <div className="rounded-lg border border-white/5 bg-white/[0.03] p-3 hover:bg-white/[0.05] transition-colors">
      <div className="flex items-start justify-between">
        <h4 className="font-medium text-sm pr-2">{lead.business_name}</h4>
        {lead.total_score > 0 ? (
          <span
            className={`text-xs font-bold flex-shrink-0 ${getScoreColor(lead.total_score)}`}
          >
            {Math.round(lead.total_score)}
          </span>
        ) : (
          <span className="text-xs text-gray-600 flex-shrink-0">—</span>
        )}
      </div>
      <p className="text-xs text-gray-500 mt-0.5">{lead.city}</p>

      {/* Actions */}
      <div className="flex items-center gap-1 mt-2 flex-wrap">
        {validPrev.map((prevStatus) => (
          <button
            key={prevStatus}
            onClick={() => onTransition(lead, prevStatus)}
            disabled={isLoading}
            className="p-1 rounded hover:bg-white/10 text-gray-500 disabled:opacity-50"
            title={`Mover a ${PIPELINE_STAGES.find((s) => s.key === prevStatus)?.label}`}
          >
            <ArrowLeft className="w-3.5 h-3.5" />
          </button>
        ))}

        {lead.email && validNext.length > 0 && (
          <button
            onClick={() => onSendEmail(lead)}
            disabled={isLoading}
            className="p-1 rounded hover:bg-white/10 text-eko-blue disabled:opacity-50"
            title="Enviar email"
          >
            <Send className="w-3.5 h-3.5" />
          </button>
        )}

        {validNext.map((nextStatus) => (
          <button
            key={nextStatus}
            onClick={() => onTransition(lead, nextStatus)}
            disabled={isLoading}
            className="p-1 rounded hover:bg-white/10 text-gray-500 disabled:opacity-50"
            title={`Mover a ${PIPELINE_STAGES.find((s) => s.key === nextStatus)?.label}`}
          >
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        ))}
      </div>
    </div>
  );
});

// ------------------------------------------------------------------
// Column Component
// ------------------------------------------------------------------

interface KanbanColumnProps {
  stage: (typeof PIPELINE_STAGES)[number];
  onTransition: (lead: Lead, newStatus: string) => void;
  onSendEmail: (lead: Lead) => void;
  actionLoading: Record<number, boolean>;
}

const KanbanColumn = memo(function KanbanColumn({
  stage,
  onTransition,
  onSendEmail,
  actionLoading,
}: KanbanColumnProps) {
  const {
    data,
    error,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    status,
  } = useColumnLeads(stage.key);

  // Flatten pages into a single array
  const stageLeads = data?.pages.flatMap((page) => page.items) || [];
  const total = data?.pages[0]?.total || 0;

  const isLoading = status === "pending";

  return (
    <div className="w-72 flex-shrink-0 rounded-xl border border-white/5 bg-white/[0.02] flex flex-col h-[600px]">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/5 flex-shrink-0">
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${stage.color}`} />
          <span className="text-sm font-medium">{stage.label}</span>
        </div>
        <span className="text-xs text-gray-500 bg-white/5 px-2 py-0.5 rounded-full">
          {total}
        </span>
      </div>

      {/* Lead List */}
      <div className="p-3 overflow-y-auto flex-1">
        {error ? (
          <div className="text-center py-8 text-red-400 text-xs">
            Error cargando leads
          </div>
        ) : isLoading && stageLeads.length === 0 ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-5 h-5 animate-spin text-eko-blue" />
          </div>
        ) : stageLeads.length === 0 ? (
          <div className="text-center py-8 text-gray-600 text-xs">No leads</div>
        ) : (
          <div className="space-y-2">
            {stageLeads.map((lead) => (
              <LeadCard
                key={lead.id}
                lead={lead}
                isLoading={!!actionLoading[lead.id]}
                onTransition={onTransition}
                onSendEmail={onSendEmail}
              />
            ))}
          </div>
        )}

        {hasNextPage && (
          <button
            onClick={() => fetchNextPage()}
            disabled={isFetchingNextPage}
            className="w-full mt-3 py-2 text-xs text-gray-500 hover:text-white transition-colors border border-white/5 rounded-lg hover:bg-white/5 disabled:opacity-50"
          >
            {isFetchingNextPage ? (
              <Loader2 className="w-4 h-4 animate-spin mx-auto" />
            ) : (
              "Cargar más"
            )}
          </button>
        )}
      </div>
    </div>
  );
});

// ------------------------------------------------------------------
// Board Component
// ------------------------------------------------------------------

export default function KanbanBoard() {
  const queryClient = useQueryClient();
  const [actionLoading, setActionLoading] = useState<Record<number, boolean>>({});
  const [isRefreshing, setIsRefreshing] = useState(false);

  const [transitionError, setTransitionError] = useState<string | null>(null);

  const transitionLead = useCallback(
    async (lead: Lead, newStatus: string) => {
      setActionLoading((prev) => ({ ...prev, [lead.id]: true }));
      setTransitionError(null);
      try {
        await crmApi.transition(lead.id, newStatus);
        // Invalidate both source and destination columns
        await queryClient.invalidateQueries({
          queryKey: ["leads", "kanban", lead.status],
        });
        await queryClient.invalidateQueries({
          queryKey: ["leads", "kanban", newStatus],
        });
      } catch (err: any) {
        console.error("Transition failed:", err);
        const msg = err.response?.data?.detail || "Transición no permitida";
        setTransitionError(msg);
        setTimeout(() => setTransitionError(null), 5000);
      } finally {
        setActionLoading((prev) => ({ ...prev, [lead.id]: false }));
      }
    },
    [queryClient]
  );

  const [emailError, setEmailError] = useState<string | null>(null);

  const sendEmail = useCallback(
    async (lead: Lead) => {
      setActionLoading((prev) => ({ ...prev, [lead.id]: true }));
      setEmailError(null);
      try {
        await crmApi.contact(lead.id, "email", "initial_outreach");
        await queryClient.invalidateQueries({
          queryKey: ["leads", "kanban", lead.status],
        });
      } catch (err: any) {
        console.error(err);
        const msg = err.response?.data?.detail || "Error enviando email";
        setEmailError(msg);
        setTimeout(() => setEmailError(null), 5000);
      } finally {
        setActionLoading((prev) => ({ ...prev, [lead.id]: false }));
      }
    },
    [queryClient]
  );

  const handleRefresh = useCallback(async () => {
    setIsRefreshing(true);
    await queryClient.invalidateQueries({ queryKey: ["leads", "kanban"] });
    setIsRefreshing(false);
  }, [queryClient]);

  return (
    <div className="relative">
      {/* Error toasts */}
      {transitionError && (
        <div className="fixed top-20 right-4 z-50">
          <div className="rounded-lg bg-red-500/90 backdrop-blur border border-red-400/50 px-4 py-3 shadow-lg">
            <p className="text-sm font-medium text-white">{transitionError}</p>
          </div>
        </div>
      )}
      {emailError && (
        <div className="fixed top-20 right-4 z-50">
          <div className="rounded-lg bg-red-500/90 backdrop-blur border border-red-400/50 px-4 py-3 shadow-lg">
            <p className="text-sm font-medium text-white">{emailError}</p>
          </div>
        </div>
      )}
      <div className="flex items-center justify-end mb-4">
        <button
          onClick={handleRefresh}
          disabled={isRefreshing}
          className="flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-xs font-medium text-gray-300 hover:bg-white/10 disabled:opacity-50 transition-colors"
        >
          {isRefreshing ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
          ) : (
            <RefreshCw className="w-3.5 h-3.5" />
          )}
          Refrescar pipeline
        </button>
      </div>
      <div className="overflow-x-auto">
        <div className="flex gap-4 min-w-max pb-4">
          {PIPELINE_STAGES.map((stage) => (
            <KanbanColumn
              key={stage.key}
              stage={stage}
              onTransition={transitionLead}
              onSendEmail={sendEmail}
              actionLoading={actionLoading}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
