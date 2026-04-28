"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { proposalsApi, dealsApi } from "@/lib/api";
import {
  FileText,
  Plus,
  Search,
  Send,
  Copy,
  Trash2,
  Eye,
  CheckCircle,
  XCircle,
  Clock,
  Loader2,
  AlertCircle,
  ExternalLink,
  Wand2,
  ChevronRight,
} from "lucide-react";

interface Proposal {
  id: number;
  deal_id: number;
  title: string;
  status: "draft" | "sent" | "accepted" | "rejected" | "expired";
  share_token: string | null;
  views_count: number | null;
  brand_primary_color: string | null;
  created_at: string;
  updated_at: string;
  deal?: {
    id: number;
    name: string;
    value: number;
    status: string;
    lead_id: number;
  } | null;
}

const statusConfig: Record<string, { label: string; color: string; icon: any }> = {
  draft: { label: "Borrador", color: "bg-gray-100 text-gray-700", icon: FileText },
  sent: { label: "Enviada", color: "bg-blue-100 text-blue-700", icon: Send },
  accepted: { label: "Aceptada", color: "bg-green-100 text-green-700", icon: CheckCircle },
  rejected: { label: "Rechazada", color: "bg-red-100 text-red-700", icon: XCircle },
  expired: { label: "Expirada", color: "bg-amber-100 text-amber-700", icon: Clock },
};

export default function ProposalsPage() {
  const router = useRouter();
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [deals, setDeals] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createData, setCreateData] = useState({ deal_id: "", title: "" });
  const [creating, setCreating] = useState(false);
  const [generatingId, setGeneratingId] = useState<number | null>(null);
  const [sendingId, setSendingId] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    loadProposals();
    loadDeals();
  }, []);

  async function loadProposals() {
    setLoading(true);
    try {
      const res = await proposalsApi.list({ limit: 100 });
      setProposals(res.data.items || []);
    } catch (e: any) {
      setError(e.response?.data?.detail || "Error cargando propuestas");
    } finally {
      setLoading(false);
    }
  }

  async function loadDeals() {
    try {
      const res = await dealsApi.list({ limit: 200 });
      setDeals(res.data.items || []);
    } catch {}
  }

  async function handleCreate() {
    if (!createData.deal_id || !createData.title) return;
    setCreating(true);
    try {
      await proposalsApi.create({
        deal_id: parseInt(createData.deal_id),
        title: createData.title,
      });
      setShowCreateModal(false);
      setCreateData({ deal_id: "", title: "" });
      loadProposals();
    } catch (e: any) {
      setError(e.response?.data?.detail || "Error creando propuesta");
    } finally {
      setCreating(false);
    }
  }

  async function handleGenerate(proposalId: number) {
    setGeneratingId(proposalId);
    try {
      await proposalsApi.generate(proposalId);
      loadProposals();
    } catch (e: any) {
      setError(e.response?.data?.detail || "Error generando propuesta");
    } finally {
      setGeneratingId(null);
    }
  }

  async function handleSend(proposalId: number) {
    setSendingId(proposalId);
    try {
      await proposalsApi.send(proposalId);
      loadProposals();
    } catch (e: any) {
      setError(e.response?.data?.detail || "Error enviando propuesta");
    } finally {
      setSendingId(null);
    }
  }

  async function handleDelete(proposalId: number) {
    if (!confirm("¿Eliminar esta propuesta?")) return;
    setDeletingId(proposalId);
    try {
      await proposalsApi.delete(proposalId);
      loadProposals();
    } catch (e: any) {
      setError(e.response?.data?.detail || "Error eliminando propuesta");
    } finally {
      setDeletingId(null);
    }
  }

  async function handleDuplicate(proposalId: number) {
    try {
      await proposalsApi.duplicate(proposalId);
      loadProposals();
    } catch (e: any) {
      setError(e.response?.data?.detail || "Error duplicando propuesta");
    }
  }

  const filtered = proposals.filter((p) => {
    const matchSearch =
      !search ||
      p.title.toLowerCase().includes(search.toLowerCase()) ||
      (p.deal?.name || "").toLowerCase().includes(search.toLowerCase());
    const matchStatus = !statusFilter || p.status === statusFilter;
    return matchSearch && matchStatus;
  });

  const stats = {
    total: proposals.length,
    draft: proposals.filter((p) => p.status === "draft").length,
    sent: proposals.filter((p) => p.status === "sent").length,
    accepted: proposals.filter((p) => p.status === "accepted").length,
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 py-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Propuestas</h1>
            <p className="text-sm text-gray-500 mt-1">
              Gestiona y envía propuestas personalizadas con IA
            </p>
          </div>
          <button
            onClick={() => setShowCreateModal(true)}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            <Plus className="w-4 h-4" />
            Nueva Propuesta
          </button>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
          {[
            { label: "Total", value: stats.total, color: "bg-gray-100" },
            { label: "Borradores", value: stats.draft, color: "bg-amber-50" },
            { label: "Enviadas", value: stats.sent, color: "bg-blue-50" },
            { label: "Aceptadas", value: stats.accepted, color: "bg-green-50" },
          ].map((s) => (
            <div key={s.label} className={`${s.color} rounded-xl p-4`}>
              <p className="text-2xl font-bold text-gray-900">{s.value}</p>
              <p className="text-sm text-gray-600">{s.label}</p>
            </div>
          ))}
        </div>

        {/* Filters */}
        <div className="flex flex-col sm:flex-row gap-3 mb-4">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              placeholder="Buscar propuestas..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Todos los estados</option>
            <option value="draft">Borrador</option>
            <option value="sent">Enviada</option>
            <option value="accepted">Aceptada</option>
            <option value="rejected">Rechazada</option>
            <option value="expired">Expirada</option>
          </select>
        </div>

        {/* Error */}
        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2 text-red-700 text-sm">
            <AlertCircle className="w-4 h-4" />
            {error}
          </div>
        )}

        {/* Proposals List */}
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
          </div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-12 bg-white rounded-xl border border-gray-200">
            <FileText className="w-12 h-12 text-gray-300 mx-auto mb-3" />
            <p className="text-gray-500">No hay propuestas</p>
            <button
              onClick={() => setShowCreateModal(true)}
              className="mt-2 text-blue-600 hover:text-blue-700 text-sm font-medium"
            >
              Crear la primera propuesta
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            {filtered.map((proposal) => {
              const cfg = statusConfig[proposal.status] || statusConfig.draft;
              const Icon = cfg.icon;
              return (
                <div
                  key={proposal.id}
                  className="bg-white rounded-xl border border-gray-200 p-4 hover:shadow-md transition-shadow"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span
                          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${cfg.color}`}
                        >
                          <Icon className="w-3 h-3" />
                          {cfg.label}
                        </span>
                        {proposal.views_count ? (
                          <span className="text-xs text-gray-500 flex items-center gap-1">
                            <Eye className="w-3 h-3" />
                            {proposal.views_count} vistas
                          </span>
                        ) : null}
                      </div>
                      <h3 className="font-semibold text-gray-900 truncate">
                        {proposal.title}
                      </h3>
                      <p className="text-sm text-gray-500">
                        {proposal.deal?.name || "Sin deal asociado"} ·{" "}
                        {proposal.deal?.value
                          ? `$${proposal.deal.value.toLocaleString()}`
                          : ""}
                      </p>
                      <p className="text-xs text-gray-400 mt-1">
                        Creada{" "}
                        {new Date(proposal.created_at).toLocaleDateString("es-MX")}
                      </p>
                    </div>

                    <div className="flex items-center gap-1 ml-4">
                      {proposal.status === "draft" && (
                        <>
                          <button
                            onClick={() => handleGenerate(proposal.id)}
                            disabled={generatingId === proposal.id}
                            title="Generar con IA"
                            className="p-2 text-purple-600 hover:bg-purple-50 rounded-lg transition-colors"
                          >
                            {generatingId === proposal.id ? (
                              <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                              <Wand2 className="w-4 h-4" />
                            )}
                          </button>
                          <button
                            onClick={() => handleSend(proposal.id)}
                            disabled={sendingId === proposal.id}
                            title="Enviar"
                            className="p-2 text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                          >
                            {sendingId === proposal.id ? (
                              <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                              <Send className="w-4 h-4" />
                            )}
                          </button>
                        </>
                      )}
                      {proposal.status === "sent" && proposal.share_token && (
                        <a
                          href={`/proposals/public/${proposal.share_token}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          title="Ver pública"
                          className="p-2 text-green-600 hover:bg-green-50 rounded-lg transition-colors"
                        >
                          <ExternalLink className="w-4 h-4" />
                        </a>
                      )}
                      <button
                        onClick={() => handleDuplicate(proposal.id)}
                        title="Duplicar"
                        className="p-2 text-gray-500 hover:bg-gray-100 rounded-lg transition-colors"
                      >
                        <Copy className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() =>
                          router.push(`/proposals/${proposal.id}`)
                        }
                        title="Editar"
                        className="p-2 text-gray-500 hover:bg-gray-100 rounded-lg transition-colors"
                      >
                        <ChevronRight className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => handleDelete(proposal.id)}
                        disabled={deletingId === proposal.id}
                        title="Eliminar"
                        className="p-2 text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                      >
                        {deletingId === proposal.id ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <Trash2 className="w-4 h-4" />
                        )}
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Create Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl p-6 w-full max-w-md">
            <h2 className="text-lg font-bold text-gray-900 mb-4">
              Nueva Propuesta
            </h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Deal
                </label>
                <select
                  value={createData.deal_id}
                  onChange={(e) =>
                    setCreateData({ ...createData, deal_id: e.target.value })
                  }
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">Selecciona un deal</option>
                  {deals.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name} (${d.value?.toLocaleString() || 0})
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Título
                </label>
                <input
                  type="text"
                  value={createData.title}
                  onChange={(e) =>
                    setCreateData({ ...createData, title: e.target.value })
                  }
                  placeholder="Ej: Propuesta de Rediseño Web"
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>
            <div className="flex gap-3 mt-6">
              <button
                onClick={() => setShowCreateModal(false)}
                className="flex-1 px-4 py-2 border border-gray-200 text-gray-700 rounded-lg hover:bg-gray-50"
              >
                Cancelar
              </button>
              <button
                onClick={handleCreate}
                disabled={creating || !createData.deal_id || !createData.title}
                className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
              >
                {creating ? (
                  <Loader2 className="w-4 h-4 animate-spin mx-auto" />
                ) : (
                  "Crear"
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
