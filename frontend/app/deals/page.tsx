"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  DndContext,
  DragOverlay,
  useDraggable,
  useDroppable,
  PointerSensor,
  TouchSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import {
  Briefcase,
  Plus,
  Loader2,
  DollarSign,
  TrendingUp,
  Target,
  Calendar,
  ArrowRight,
  X,
  CheckCircle,
  GripVertical,
} from "lucide-react";
import Navbar from "@/components/Navbar";
import { dealsApi, leadsApi } from "@/lib/api";

interface Deal {
  id: number;
  lead_id: number;
  name: string;
  value: number;
  probability: number;
  status: string;
  expected_close_date: string | null;
  description: string | null;
  assigned_to: string | null;
  created_at: string;
}

interface Forecast {
  total_pipeline_value: number;
  total_weighted_value: number;
  expected_revenue_this_month: number;
  expected_revenue_this_quarter: number;
  deals_count: number;
  closed_won_count: number;
  closed_won_value: number;
  closed_lost_count: number;
  closed_lost_value: number;
  total_revenue: number;
}

const DEAL_STATUSES = [
  { key: "prospecting", label: "Prospecting", color: "bg-gray-500/10 text-gray-400 border-gray-500/20" },
  { key: "qualification", label: "Qualification", color: "bg-blue-500/10 text-blue-400 border-blue-500/20" },
  { key: "proposal", label: "Proposal", color: "bg-gold/10 text-gold border-gold/20" },
  { key: "negotiation", label: "Negotiation", color: "bg-orange-500/10 text-orange-400 border-orange-500/20" },
  { key: "closed_won", label: "Closed Won", color: "bg-eko-green/10 text-eko-green border-eko-green/20" },
  { key: "closed_lost", label: "Closed Lost", color: "bg-red-500/10 text-red-400 border-red-500/20" },
];

function DealCard({
  deal,
  isOverlay,
}: {
  deal: Deal;
  isOverlay?: boolean;
}) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: `deal-${deal.id}`,
    data: { deal },
  });

  const formatCurrency = (val: number) =>
    new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      maximumFractionDigits: 0,
    }).format(val);

  if (isDragging && !isOverlay) {
    return (
      <div
        ref={setNodeRef}
        className="rounded-lg border border-dashed border-white/20 bg-white/5 p-3 opacity-50 h-[80px]"
      />
    );
  }

  return (
    <div
      ref={setNodeRef}
      {...listeners}
      {...attributes}
      className={`group rounded-lg border border-white/5 bg-white/5 p-3 hover:border-white/10 transition-all cursor-grab active:cursor-grabbing ${
        isOverlay ? "shadow-xl rotate-2 scale-105 z-50" : ""
      }`}
    >
      <Link
        href={`/deals/${deal.id}`}
        onPointerDown={(e) => e.stopPropagation()}
        onClick={(e) => {
          if (isDragging) e.preventDefault();
        }}
        className="block"
      >
        <div className="flex items-start justify-between gap-2">
          <p className="text-sm font-medium truncate flex-1">{deal.name}</p>
          <GripVertical className="w-3.5 h-3.5 text-gray-600 opacity-0 group-hover:opacity-100 transition-opacity shrink-0" />
        </div>
        <p className="text-xs text-gray-500 mt-0.5">
          {formatCurrency(deal.value)} • {deal.probability}%
        </p>
        {deal.expected_close_date && (
          <p className="text-[10px] text-gray-600 mt-1 flex items-center gap-1">
            <Calendar className="w-3 h-3" />
            {new Date(deal.expected_close_date).toLocaleDateString("es-ES", {
              day: "numeric",
              month: "short",
            })}
          </p>
        )}
      </Link>
    </div>
  );
}

function DealColumn({
  status,
  deals,
  children,
}: {
  status: (typeof DEAL_STATUSES)[number];
  deals: Deal[];
  children: React.ReactNode;
}) {
  const { setNodeRef, isOver } = useDroppable({
    id: `column-${status.key}`,
    data: { status: status.key },
  });

  const totalValue = deals.reduce((sum, d) => sum + (d.value || 0), 0);
  const formatCurrency = (val: number) =>
    new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      maximumFractionDigits: 0,
    }).format(val);

  return (
    <div className="flex flex-col min-w-[200px]">
      <div className={`flex items-center justify-between px-3 py-2 rounded-t-lg border border-b-0 ${status.color}`}>
        <span className="text-xs font-medium">{status.label}</span>
        <span className="text-xs opacity-70">{deals.length}</span>
      </div>
      <div
        ref={setNodeRef}
        className={`flex-1 rounded-b-lg border border-white/5 p-2 space-y-2 min-h-[200px] transition-colors ${
          isOver ? "bg-white/[0.04] border-eko-blue/30" : "bg-white/[0.02]"
        }`}
      >
        {children}
        {deals.length > 0 && (
          <div className="text-[10px] text-gray-600 text-center pt-1">
            Total: {formatCurrency(totalValue)}
          </div>
        )}
      </div>
    </div>
  );
}

export default function DealsPage() {
  const router = useRouter();
  const [deals, setDeals] = useState<Deal[]>([]);
  const [forecast, setForecast] = useState<Forecast | null>(null);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [leads, setLeads] = useState<{ id: number; business_name: string }[]>([]);
  const [activeDeal, setActiveDeal] = useState<Deal | null>(null);
  const [updatingId, setUpdatingId] = useState<number | null>(null);

  // Create form
  const [newDeal, setNewDeal] = useState({
    lead_id: "",
    name: "",
    value: "",
    probability: "20",
    expected_close_date: "",
    description: "",
  });

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 200, tolerance: 5 } })
  );

  const loadDeals = useCallback(async () => {
    setLoading(true);
    try {
      const [dealsRes, forecastRes] = await Promise.all([
        dealsApi.list({ limit: 200 }),
        dealsApi.forecast(),
      ]);
      setDeals(dealsRes.data?.items || []);
      setForecast(forecastRes.data);
    } catch (err) {
      console.error("Failed to load deals:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDeals();
    leadsApi.list({ page_size: 200 }).then((res) => {
      setLeads(res.data?.items?.map((l: any) => ({ id: l.id, business_name: l.business_name })) || []);
    });
  }, [loadDeals]);

  const handleCreate = async () => {
    if (!newDeal.lead_id || !newDeal.name.trim()) return;
    setCreating(true);
    try {
      await dealsApi.create({
        lead_id: parseInt(newDeal.lead_id),
        name: newDeal.name.trim(),
        value: parseFloat(newDeal.value) || 0,
        probability: parseInt(newDeal.probability) || 20,
        expected_close_date: newDeal.expected_close_date || undefined,
        description: newDeal.description || undefined,
      });
      setShowCreate(false);
      setNewDeal({ lead_id: "", name: "", value: "", probability: "20", expected_close_date: "", description: "" });
      loadDeals();
    } catch (err) {
      console.error(err);
      alert("Error creating deal");
    } finally {
      setCreating(false);
    }
  };

  const handleDragStart = (event: DragStartEvent) => {
    const deal = event.active.data.current?.deal as Deal;
    if (deal) setActiveDeal(deal);
  };

  const handleDragEnd = async (event: DragEndEvent) => {
    setActiveDeal(null);
    const { active, over } = event;
    if (!over) return;

    const deal = active.data.current?.deal as Deal;
    const targetStatus = over.data.current?.status as string;
    if (!deal || !targetStatus || deal.status === targetStatus) return;

    // Optimistic UI
    setDeals((prev) =>
      prev.map((d) => (d.id === deal.id ? { ...d, status: targetStatus } : d))
    );
    setUpdatingId(deal.id);

    try {
      await dealsApi.update(deal.id, { status: targetStatus });
      const forecastRes = await dealsApi.forecast();
      setForecast(forecastRes.data);
    } catch (err) {
      console.error("Failed to update deal status:", err);
      // Revert
      setDeals((prev) =>
        prev.map((d) => (d.id === deal.id ? { ...d, status: deal.status } : d))
      );
      alert("Error moviendo el deal");
    } finally {
      setUpdatingId(null);
    }
  };

  const formatCurrency = (val: number) =>
    new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      maximumFractionDigits: 0,
    }).format(val);

  const dealsByStatus = (status: string) => deals.filter((d) => d.status === status);

  return (
    <div className="min-h-screen bg-eko-graphite">
      <Navbar />
      <main className="pt-20 pb-12 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-eko-blue/10 text-eko-blue">
              <Briefcase className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-2xl font-bold font-display">Deals</h1>
              <p className="text-gray-400 text-sm">Pipeline de oportunidades</p>
            </div>
          </div>
          <button
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-2 rounded-lg bg-eko-blue px-4 py-2 text-sm font-medium hover:bg-eko-blue-dark transition-colors"
          >
            <Plus className="w-4 h-4" />
            Nuevo deal
          </button>
        </div>

        {/* Forecast Cards */}
        {forecast && (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4 mb-8">
            <div className="rounded-xl border border-white/5 bg-white/[0.02] p-4">
              <div className="flex items-center gap-2 mb-2">
                <DollarSign className="w-4 h-4 text-eko-blue" />
                <span className="text-xs text-gray-500">Pipeline</span>
              </div>
              <p className="text-lg font-bold">{formatCurrency(forecast.total_pipeline_value)}</p>
            </div>
            <div className="rounded-xl border border-white/5 bg-white/[0.02] p-4">
              <div className="flex items-center gap-2 mb-2">
                <TrendingUp className="w-4 h-4 text-eko-green" />
                <span className="text-xs text-gray-500">Weighted</span>
              </div>
              <p className="text-lg font-bold text-eko-green">{formatCurrency(forecast.total_weighted_value)}</p>
            </div>
            <div className="rounded-xl border border-white/5 bg-white/[0.02] p-4">
              <div className="flex items-center gap-2 mb-2">
                <Target className="w-4 h-4 text-gold" />
                <span className="text-xs text-gray-500">Este Mes</span>
              </div>
              <p className="text-lg font-bold">{formatCurrency(forecast.expected_revenue_this_month)}</p>
            </div>
            <div className="rounded-xl border border-white/5 bg-white/[0.02] p-4">
              <div className="flex items-center gap-2 mb-2">
                <Briefcase className="w-4 h-4 text-gray-400" />
                <span className="text-xs text-gray-500">Abiertos</span>
              </div>
              <p className="text-lg font-bold">{forecast.deals_count}</p>
            </div>
            <div className="rounded-xl border border-white/5 bg-white/[0.02] p-4">
              <div className="flex items-center gap-2 mb-2">
                <CheckCircle className="w-4 h-4 text-eko-green" />
                <span className="text-xs text-gray-500">Ganados</span>
              </div>
              <p className="text-lg font-bold text-eko-green">{formatCurrency(forecast.closed_won_value)}</p>
              <p className="text-[10px] text-gray-600">{forecast.closed_won_count} deals</p>
            </div>
            <div className="rounded-xl border border-white/5 bg-white/[0.02] p-4">
              <div className="flex items-center gap-2 mb-2">
                <X className="w-4 h-4 text-red-400" />
                <span className="text-xs text-gray-500">Perdidos</span>
              </div>
              <p className="text-lg font-bold text-red-400">{formatCurrency(forecast.closed_lost_value)}</p>
              <p className="text-[10px] text-gray-600">{forecast.closed_lost_count} deals</p>
            </div>
          </div>
        )}

        {/* Create modal */}
        {showCreate && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
            <div className="w-full max-w-md rounded-xl border border-white/10 bg-eko-graphite p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-medium">Nuevo Deal</h3>
                <button onClick={() => setShowCreate(false)} className="text-gray-400 hover:text-white">
                  <X className="w-4 h-4" />
                </button>
              </div>
              <div className="space-y-3">
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Lead</label>
                  <select
                    value={newDeal.lead_id}
                    onChange={(e) => setNewDeal({ ...newDeal, lead_id: e.target.value })}
                    className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm focus:border-eko-blue focus:outline-none"
                  >
                    <option value="">Seleccionar lead...</option>
                    {leads.map((l) => (
                      <option key={l.id} value={l.id}>{l.business_name}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Nombre del deal</label>
                  <input
                    type="text"
                    value={newDeal.name}
                    onChange={(e) => setNewDeal({ ...newDeal, name: e.target.value })}
                    placeholder="Ej: Website redesign project"
                    className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm focus:border-eko-blue focus:outline-none"
                  />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">Valor ($)</label>
                    <input
                      type="number"
                      value={newDeal.value}
                      onChange={(e) => setNewDeal({ ...newDeal, value: e.target.value })}
                      placeholder="5000"
                      className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm focus:border-eko-blue focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">Probabilidad (%)</label>
                    <input
                      type="number"
                      value={newDeal.probability}
                      onChange={(e) => setNewDeal({ ...newDeal, probability: e.target.value })}
                      min={0}
                      max={100}
                      className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm focus:border-eko-blue focus:outline-none"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Fecha de cierre esperada</label>
                  <input
                    type="date"
                    value={newDeal.expected_close_date}
                    onChange={(e) => setNewDeal({ ...newDeal, expected_close_date: e.target.value })}
                    className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm focus:border-eko-blue focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Descripción</label>
                  <textarea
                    value={newDeal.description}
                    onChange={(e) => setNewDeal({ ...newDeal, description: e.target.value })}
                    placeholder="Detalles del deal..."
                    rows={3}
                    className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm focus:border-eko-blue focus:outline-none"
                  />
                </div>
                <div className="flex gap-2 pt-2">
                  <button
                    onClick={handleCreate}
                    disabled={creating || !newDeal.lead_id || !newDeal.name.trim()}
                    className="flex-1 rounded-lg bg-eko-blue px-4 py-2 text-sm font-medium hover:bg-eko-blue-dark disabled:opacity-50 transition-colors"
                  >
                    {creating ? <Loader2 className="w-4 h-4 animate-spin mx-auto" /> : "Crear Deal"}
                  </button>
                  <button
                    onClick={() => setShowCreate(false)}
                    className="rounded-lg border border-white/10 px-4 py-2 text-sm text-gray-400 hover:bg-white/5 transition-colors"
                  >
                    Cancelar
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* DnD Kanban */}
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-8 h-8 animate-spin text-eko-blue" />
          </div>
        ) : deals.length === 0 ? (
          <div className="text-center py-20 text-gray-500">
            <Briefcase className="w-12 h-12 mb-4 mx-auto opacity-50" />
            <p className="text-lg font-medium">No hay deals</p>
            <p className="text-sm mt-1">Crea tu primer deal para empezar a trackear oportunidades.</p>
          </div>
        ) : (
          <DndContext
            sensors={sensors}
            onDragStart={handleDragStart}
            onDragEnd={handleDragEnd}
          >
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
              {DEAL_STATUSES.map((status) => (
                <DealColumn
                  key={status.key}
                  status={status}
                  deals={dealsByStatus(status.key)}
                >
                  {dealsByStatus(status.key).map((deal) => (
                    <DealCard key={deal.id} deal={deal} />
                  ))}
                </DealColumn>
              ))}
            </div>
            <DragOverlay>
              {activeDeal ? <DealCard deal={activeDeal} isOverlay /> : null}
            </DragOverlay>
          </DndContext>
        )}
      </main>
    </div>
  );
}
