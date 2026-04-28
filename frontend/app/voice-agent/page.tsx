"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { voiceAgentApi, leadsApi } from "@/lib/api";
import {
  Phone,
  PhoneCall,
  Play,
  Loader2,
  AlertCircle,
  Clock,
  CheckCircle,
  XCircle,
  Voicemail,
  User,
  Settings,
  Plus,
  Search,
  Mic,
  BarChart3,
  ChevronRight,
  ExternalLink,
} from "lucide-react";

interface VoiceCall {
  id: number;
  lead_id: number;
  lead_name: string | null;
  lead_phone: string | null;
  result: string;
  notes: string | null;
  interest_level: string | null;
  next_action: string | null;
  call_duration_seconds: number | null;
  scheduled_at: string | null;
  completed_at: string | null;
  created_at: string;
}

const resultConfig: Record<string, { label: string; color: string; icon: any }> = {
  SCHEDULED: { label: "Programada", color: "text-amber-400", icon: Clock },
  INITIATED: { label: "Iniciada", color: "text-blue-400", icon: PhoneCall },
  COMPLETED: { label: "Completada", color: "text-green-400", icon: CheckCircle },
  VOICEMAIL: { label: "Buzón de voz", color: "text-purple-400", icon: Voicemail },
  NO_ANSWER: { label: "Sin respuesta", color: "text-gray-400", icon: XCircle },
  BUSY: { label: "Ocupado", color: "text-orange-400", icon: Phone },
  FAILED: { label: "Fallida", color: "text-red-400", icon: AlertCircle },
};

export default function VoiceAgentPage() {
  const router = useRouter();
  const [calls, setCalls] = useState<VoiceCall[]>([]);
  const [loading, setLoading] = useState(true);
  const [configLoading, setConfigLoading] = useState(true);
  const [config, setConfig] = useState({ configured: false });
  const [leads, setLeads] = useState<any[]>([]);
  const [searchLead, setSearchLead] = useState("");
  const [showCallModal, setShowCallModal] = useState(false);
  const [selectedLead, setSelectedLead] = useState<number | null>(null);
  const [callInstructions, setCallInstructions] = useState("");
  const [startingCall, setStartingCall] = useState(false);
  const [error, setError] = useState("");
  const [statusFilter, setStatusFilter] = useState("");

  useEffect(() => {
    loadCalls();
    loadConfig();
    loadLeads();
  }, []);

  async function loadCalls() {
    setLoading(true);
    try {
      const res = await voiceAgentApi.listCalls({ limit: 100 });
      setCalls(res.data.items || []);
    } catch (e: any) {
      setError(e.response?.data?.detail || "Error cargando llamadas");
    } finally {
      setLoading(false);
    }
  }

  async function loadConfig() {
    setConfigLoading(true);
    try {
      const res = await voiceAgentApi.getConfig();
      setConfig(res.data);
    } catch {}
    setConfigLoading(false);
  }

  async function loadLeads() {
    try {
      const res = await leadsApi.list({ page_size: 200 });
      setLeads(res.data.items || []);
    } catch {}
  }

  async function handleStartCall() {
    if (!selectedLead) return;
    setStartingCall(true);
    setError("");
    try {
      await voiceAgentApi.startCall({
        lead_id: selectedLead,
        custom_instructions: callInstructions || undefined,
        schedule_now: true,
      });
      setShowCallModal(false);
      setSelectedLead(null);
      setCallInstructions("");
      loadCalls();
    } catch (e: any) {
      setError(e.response?.data?.detail || "Error iniciando llamada");
    } finally {
      setStartingCall(false);
    }
  }

  const filteredLeads = leads.filter((l) =>
    !searchLead ||
    l.business_name?.toLowerCase().includes(searchLead.toLowerCase()) ||
    l.phone?.includes(searchLead)
  );

  const filteredCalls = calls.filter((c) =>
    !statusFilter || c.result === statusFilter
  );

  const stats = {
    total: calls.length,
    completed: calls.filter((c) => c.result === "COMPLETED").length,
    voicemail: calls.filter((c) => c.result === "VOICEMAIL").length,
    no_answer: calls.filter((c) => c.result === "NO_ANSWER").length,
    high_interest: calls.filter((c) => c.interest_level === "HIGH").length,
  };

  const formatDuration = (seconds: number | null) => {
    if (!seconds) return "0:00";
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${s.toString().padStart(2, "0")}`;
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 py-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Voice Agent</h1>
            <p className="text-sm text-gray-500 mt-1">
              Llamadas automatizadas con IA via VAPI
            </p>
          </div>
          <div className="flex items-center gap-3">
            {!configLoading && !config.configured && (
              <div className="flex items-center gap-2 px-3 py-1.5 bg-amber-50 text-amber-700 rounded-lg text-sm">
                <AlertCircle className="w-4 h-4" />
                VAPI API Key no configurada
              </div>
            )}
            <button
              onClick={() => setShowCallModal(true)}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            >
              <PhoneCall className="w-4 h-4" />
              Nueva Llamada
            </button>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
          {[
            { label: "Total", value: stats.total, color: "bg-gray-100" },
            { label: "Completadas", value: stats.completed, color: "bg-green-50" },
            { label: "Buzón", value: stats.voicemail, color: "bg-purple-50" },
            { label: "Sin respuesta", value: stats.no_answer, color: "bg-gray-50" },
            { label: "Alto interés", value: stats.high_interest, color: "bg-blue-50" },
          ].map((s) => (
            <div key={s.label} className={`${s.color} rounded-xl p-4`}>
              <p className="text-2xl font-bold text-gray-900">{s.value}</p>
              <p className="text-sm text-gray-600">{s.label}</p>
            </div>
          ))}
        </div>

        {/* Filters */}
        <div className="flex flex-col sm:flex-row gap-3 mb-4">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Todos los resultados</option>
            <option value="COMPLETED">Completadas</option>
            <option value="VOICEMAIL">Buzón de voz</option>
            <option value="NO_ANSWER">Sin respuesta</option>
            <option value="BUSY">Ocupado</option>
            <option value="FAILED">Fallidas</option>
            <option value="SCHEDULED">Programadas</option>
          </select>
        </div>

        {/* Error */}
        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2 text-red-700 text-sm">
            <AlertCircle className="w-4 h-4" />
            {error}
          </div>
        )}

        {/* Calls List */}
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
          </div>
        ) : filteredCalls.length === 0 ? (
          <div className="text-center py-12 bg-white rounded-xl border border-gray-200">
            <Phone className="w-12 h-12 text-gray-300 mx-auto mb-3" />
            <p className="text-gray-500">No hay llamadas registradas</p>
            <button
              onClick={() => setShowCallModal(true)}
              className="mt-2 text-blue-600 hover:text-blue-700 text-sm font-medium"
            >
              Iniciar la primera llamada
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            {filteredCalls.map((call) => {
              const cfg = resultConfig[call.result] || resultConfig.SCHEDULED;
              const Icon = cfg.icon;
              return (
                <div
                  key={call.id}
                  className="bg-white rounded-xl border border-gray-200 p-4 hover:shadow-md transition-shadow"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${cfg.color}`}>
                          <Icon className="w-3 h-3" />
                          {cfg.label}
                        </span>
                        {call.interest_level && (
                          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                            call.interest_level === "HIGH"
                              ? "bg-green-100 text-green-700"
                              : call.interest_level === "MEDIUM"
                              ? "bg-amber-100 text-amber-700"
                              : "bg-gray-100 text-gray-600"
                          }`}>
                            Interés: {call.interest_level}
                          </span>
                        )}
                      </div>
                      <h3 className="font-semibold text-gray-900">
                        {call.lead_name || "Lead desconocido"}
                      </h3>
                      <p className="text-sm text-gray-500">
                        {call.lead_phone || "Sin teléfono"}
                        {call.call_duration_seconds ? ` · ${formatDuration(call.call_duration_seconds)}` : ""}
                      </p>
                      {call.notes && (
                        <p className="text-sm text-gray-600 mt-2 line-clamp-2">
                          {call.notes}
                        </p>
                      )}
                      <p className="text-xs text-gray-400 mt-1">
                        {new Date(call.created_at).toLocaleString("es-MX")}
                      </p>
                    </div>
                    <div className="flex items-center gap-1 ml-4">
                      <button
                        onClick={() => router.push(`/leads/${call.lead_id}`)}
                        title="Ver lead"
                        className="p-2 text-gray-500 hover:bg-gray-100 rounded-lg transition-colors"
                      >
                        <ChevronRight className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Start Call Modal */}
      {showCallModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl p-6 w-full max-w-lg">
            <h2 className="text-lg font-bold text-gray-900 mb-4">
              Nueva Llamada con AI
            </h2>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Buscar Lead
                </label>
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                  <input
                    type="text"
                    placeholder="Nombre o teléfono..."
                    value={searchLead}
                    onChange={(e) => setSearchLead(e.target.value)}
                    className="w-full pl-10 pr-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>

              <div className="max-h-48 overflow-y-auto border border-gray-200 rounded-lg">
                {filteredLeads.length === 0 ? (
                  <p className="p-3 text-sm text-gray-500 text-center">No se encontraron leads</p>
                ) : (
                  filteredLeads.map((lead) => (
                    <button
                      key={lead.id}
                      onClick={() => setSelectedLead(lead.id)}
                      className={`w-full text-left px-3 py-2 text-sm border-b border-gray-100 last:border-0 transition-colors ${
                        selectedLead === lead.id
                          ? "bg-blue-50 text-blue-700"
                          : "hover:bg-gray-50 text-gray-700"
                      }`}
                    >
                      <div className="font-medium">{lead.business_name}</div>
                      <div className="text-xs text-gray-500">{lead.phone || "Sin teléfono"} · {lead.city || ""}</div>
                    </button>
                  ))
                )}
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Instrucciones personalizadas (opcional)
                </label>
                <textarea
                  value={callInstructions}
                  onChange={(e) => setCallInstructions(e.target.value)}
                  placeholder="Ej: Menciona que tenemos una promoción especial este mes..."
                  rows={3}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 text-sm"
                />
              </div>
            </div>

            <div className="flex gap-3 mt-6">
              <button
                onClick={() => setShowCallModal(false)}
                className="flex-1 px-4 py-2 border border-gray-200 text-gray-700 rounded-lg hover:bg-gray-50"
              >
                Cancelar
              </button>
              <button
                onClick={handleStartCall}
                disabled={startingCall || !selectedLead}
                className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {startingCall ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <PhoneCall className="w-4 h-4" />
                )}
                {startingCall ? "Iniciando..." : "Llamar"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
