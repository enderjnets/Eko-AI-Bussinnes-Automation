"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  Briefcase,
  ArrowLeft,
  Loader2,
  Save,
  Trash2,
  AlertTriangle,
  Calendar,
  DollarSign,
  Target,
  User,
  Mail,
  Phone,
  ExternalLink,
  CheckCircle,
  X,
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
  notes: string | null;
  source: string | null;
  assigned_to: string | null;
  lost_reason: string | null;
  actual_close_date: string | null;
  created_at: string;
  updated_at: string;
}

interface Lead {
  id: number;
  business_name: string;
  email: string | null;
  phone: string | null;
  status: string;
}

const STATUS_OPTIONS = [
  { value: "prospecting", label: "Prospecting" },
  { value: "qualification", label: "Qualification" },
  { value: "proposal", label: "Proposal" },
  { value: "negotiation", label: "Negotiation" },
  { value: "closed_won", label: "Closed Won" },
  { value: "closed_lost", label: "Closed Lost" },
];

const statusColor = (status: string) => {
  switch (status) {
    case "closed_won": return "bg-eko-green/10 text-eko-green border-eko-green/20";
    case "closed_lost": return "bg-red-500/10 text-red-400 border-red-500/20";
    case "negotiation": return "bg-orange-500/10 text-orange-400 border-orange-500/20";
    case "proposal": return "bg-gold/10 text-gold border-gold/20";
    case "qualification": return "bg-blue-500/10 text-blue-400 border-blue-500/20";
    default: return "bg-gray-500/10 text-gray-400 border-gray-500/20";
  }
};

export default function DealDetailPage() {
  const { id } = useParams();
  const router = useRouter();
  const dealId = parseInt(id as string);

  const [deal, setDeal] = useState<Deal | null>(null);
  const [lead, setLead] = useState<Lead | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [showDelete, setShowDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [saveMsg, setSaveMsg] = useState("");

  // Form state
  const [form, setForm] = useState<Partial<Deal>>({});

  useEffect(() => {
    loadDeal();
  }, [dealId]);

  const loadDeal = async () => {
    setLoading(true);
    try {
      const dealRes = await dealsApi.get(dealId);
      const d = dealRes.data;
      setDeal(d);
      setForm({ ...d });

      if (d.lead_id) {
        try {
          const leadRes = await leadsApi.get(d.lead_id);
          setLead(leadRes.data);
        } catch {
          // silently fail
        }
      }
    } catch (err) {
      console.error("Failed to load deal:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setSaveMsg("");
    try {
      const updateData = {
        name: form.name,
        value: form.value,
        probability: form.probability,
        status: form.status,
        expected_close_date: form.expected_close_date,
        description: form.description,
        notes: form.notes,
        assigned_to: form.assigned_to,
        lost_reason: form.lost_reason,
      };
      await dealsApi.update(dealId, updateData);
      setSaveMsg("Guardado correctamente");
      loadDeal();
    } catch (err: any) {
      setSaveMsg(err.response?.data?.detail || "Error guardando");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    setDeleting(true);
    try {
      await dealsApi.delete(dealId);
      router.push("/deals");
    } catch (err) {
      console.error(err);
      alert("Error eliminando deal");
      setDeleting(false);
    }
  };

  const formatCurrency = (val: number) =>
    new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      maximumFractionDigits: 0,
    }).format(val);

  if (loading) {
    return (
      <div className="min-h-screen bg-eko-graphite flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-eko-blue" />
      </div>
    );
  }

  if (!deal) {
    return (
      <div className="min-h-screen bg-eko-graphite flex items-center justify-center text-gray-500">
        <p>Deal no encontrado</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-eko-graphite">
      <Navbar />
      <main className="pt-20 pb-12 px-4 sm:px-6 lg:px-8 max-w-5xl mx-auto">
        {/* Header */}
        <div className="flex items-center gap-3 mb-6">
          <Link
            href="/deals"
            className="p-2 rounded-lg text-gray-400 hover:text-white hover:bg-white/10 transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <div className="flex-1">
            <div className="flex items-center gap-3 flex-wrap">
              <h1 className="text-2xl font-bold font-display">{deal.name}</h1>
              <span className={`text-xs px-2 py-1 rounded-full border capitalize ${statusColor(deal.status)}`}>
                {deal.status.replace("_", " ")}
              </span>
            </div>
            <p className="text-gray-400 text-sm mt-1">
              Deal #{deal.id} • Creado {new Date(deal.created_at).toLocaleDateString("es-ES")}
            </p>
          </div>
          <button
            onClick={() => setShowDelete(true)}
            className="flex items-center gap-2 rounded-lg border border-red-500/30 px-4 py-2 text-sm text-red-400 hover:bg-red-500/10 transition-colors"
          >
            <Trash2 className="w-4 h-4" />
            Eliminar
          </button>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Edit Form */}
          <div className="lg:col-span-2 space-y-6">
            <div className="rounded-xl border border-white/5 bg-white/[0.02] p-6">
              <h3 className="font-medium mb-4">Información del Deal</h3>
              <div className="space-y-4">
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Nombre</label>
                  <input
                    type="text"
                    value={form.name || ""}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                    className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm focus:border-eko-blue focus:outline-none"
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">Valor ($)</label>
                    <input
                      type="number"
                      value={form.value ?? ""}
                      onChange={(e) => setForm({ ...form, value: parseFloat(e.target.value) || 0 })}
                      className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm focus:border-eko-blue focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">Probabilidad (%)</label>
                    <input
                      type="number"
                      min={0}
                      max={100}
                      value={form.probability ?? ""}
                      onChange={(e) => setForm({ ...form, probability: parseInt(e.target.value) || 0 })}
                      className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm focus:border-eko-blue focus:outline-none"
                    />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">Status</label>
                    <select
                      value={form.status || ""}
                      onChange={(e) => setForm({ ...form, status: e.target.value })}
                      className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm focus:border-eko-blue focus:outline-none"
                    >
                      {STATUS_OPTIONS.map((s) => (
                        <option key={s.value} value={s.value}>{s.label}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">Fecha de cierre esperada</label>
                    <input
                      type="date"
                      value={form.expected_close_date ? form.expected_close_date.split("T")[0] : ""}
                      onChange={(e) => setForm({ ...form, expected_close_date: e.target.value || null })}
                      className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm focus:border-eko-blue focus:outline-none"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Descripción</label>
                  <textarea
                    value={form.description || ""}
                    onChange={(e) => setForm({ ...form, description: e.target.value })}
                    rows={3}
                    className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm focus:border-eko-blue focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Notas</label>
                  <textarea
                    value={form.notes || ""}
                    onChange={(e) => setForm({ ...form, notes: e.target.value })}
                    rows={3}
                    className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm focus:border-eko-blue focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Asignado a</label>
                  <input
                    type="text"
                    value={form.assigned_to || ""}
                    onChange={(e) => setForm({ ...form, assigned_to: e.target.value })}
                    className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm focus:border-eko-blue focus:outline-none"
                  />
                </div>
                {form.status === "closed_lost" && (
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">Razón de pérdida</label>
                    <input
                      type="text"
                      value={form.lost_reason || ""}
                      onChange={(e) => setForm({ ...form, lost_reason: e.target.value })}
                      placeholder="Ej: Precio, timing, competencia..."
                      className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm focus:border-eko-blue focus:outline-none"
                    />
                  </div>
                )}
                <div className="flex items-center gap-3 pt-2">
                  <button
                    onClick={handleSave}
                    disabled={saving}
                    className="flex items-center gap-2 rounded-lg bg-eko-blue px-4 py-2 text-sm font-medium hover:bg-eko-blue-dark disabled:opacity-50 transition-colors"
                  >
                    {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                    Guardar cambios
                  </button>
                  {saveMsg && (
                    <span className={`text-xs ${saveMsg.includes("correctamente") ? "text-eko-green" : "text-red-400"}`}>
                      {saveMsg}
                    </span>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Context Panel */}
          <div className="space-y-6">
            {/* Linked Lead */}
            {lead && (
              <div className="rounded-xl border border-white/5 bg-white/[0.02] p-5">
                <h3 className="text-sm font-medium mb-3">Lead vinculado</h3>
                <Link
                  href={`/leads/${lead.id}`}
                  className="block rounded-lg border border-white/5 bg-white/5 p-4 hover:border-white/10 transition-colors"
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium">{lead.business_name}</span>
                    <ExternalLink className="w-3.5 h-3.5 text-gray-500" />
                  </div>
                  {lead.email && (
                    <div className="flex items-center gap-2 text-xs text-gray-500 mb-1">
                      <Mail className="w-3.5 h-3.5" />
                      {lead.email}
                    </div>
                  )}
                  {lead.phone && (
                    <div className="flex items-center gap-2 text-xs text-gray-500 mb-1">
                      <Phone className="w-3.5 h-3.5" />
                      {lead.phone}
                    </div>
                  )}
                  <div className="flex items-center gap-2 text-xs text-gray-500">
                    <User className="w-3.5 h-3.5" />
                    Status: <span className="capitalize">{lead.status}</span>
                  </div>
                </Link>
              </div>
            )}

            {/* Deal Stats */}
            <div className="rounded-xl border border-white/5 bg-white/[0.02] p-5">
              <h3 className="text-sm font-medium mb-3">Resumen</h3>
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-gray-500 flex items-center gap-2">
                    <DollarSign className="w-3.5 h-3.5" /> Valor
                  </span>
                  <span className="text-sm font-medium">{formatCurrency(deal.value)}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-gray-500 flex items-center gap-2">
                    <Target className="w-3.5 h-3.5" /> Probabilidad
                  </span>
                  <span className="text-sm font-medium">{deal.probability}%</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-gray-500 flex items-center gap-2">
                    <Calendar className="w-3.5 h-3.5" /> Cierre esperado
                  </span>
                  <span className="text-sm">
                    {deal.expected_close_date
                      ? new Date(deal.expected_close_date).toLocaleDateString("es-ES")
                      : "—"}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-gray-500 flex items-center gap-2">
                    <CheckCircle className="w-3.5 h-3.5" /> Última actualización
                  </span>
                  <span className="text-sm">
                    {new Date(deal.updated_at).toLocaleDateString("es-ES")}
                  </span>
                </div>
                {deal.actual_close_date && (
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-gray-500 flex items-center gap-2">
                      <CheckCircle className="w-3.5 h-3.5 text-eko-green" /> Cierre real
                    </span>
                    <span className="text-sm text-eko-green">
                      {new Date(deal.actual_close_date).toLocaleDateString("es-ES")}
                    </span>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </main>

      {/* Delete Confirmation Modal */}
      {showDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="w-full max-w-sm rounded-xl border border-red-500/20 bg-eko-graphite p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 rounded-lg bg-red-500/10">
                <AlertTriangle className="w-5 h-5 text-red-400" />
              </div>
              <h3 className="font-medium">Eliminar deal</h3>
            </div>
            <p className="text-sm text-gray-400 mb-6">
              ¿Seguro que quieres eliminar <strong>{deal.name}</strong>? Esta acción no se puede deshacer.
            </p>
            <div className="flex gap-3">
              <button
                onClick={handleDelete}
                disabled={deleting}
                className="flex-1 rounded-lg bg-red-500 px-4 py-2 text-sm font-medium text-white hover:bg-red-600 disabled:opacity-50 transition-colors"
              >
                {deleting ? <Loader2 className="w-4 h-4 animate-spin mx-auto" /> : "Sí, eliminar"}
              </button>
              <button
                onClick={() => setShowDelete(false)}
                className="rounded-lg border border-white/10 px-4 py-2 text-sm text-gray-400 hover:bg-white/5 transition-colors"
              >
                Cancelar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
