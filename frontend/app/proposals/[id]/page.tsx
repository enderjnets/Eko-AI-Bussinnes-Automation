"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { proposalsApi, dealsApi } from "@/lib/api";
import {
  ArrowLeft,
  Send,
  Wand2,
  Save,
  Loader2,
  AlertCircle,
  ExternalLink,
  Copy,
  CheckCircle,
  FileText,
} from "lucide-react";

interface Proposal {
  id: number;
  deal_id: number;
  title: string;
  content: string | null;
  plain_text: string | null;
  status: string;
  share_token: string | null;
  views_count: number | null;
  brand_primary_color: string | null;
  brand_secondary_color: string | null;
  brand_logo_url: string | null;
  notes: string | null;
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

export default function ProposalDetailPage() {
  const { id } = useParams();
  const router = useRouter();
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [deal, setDeal] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  const [activeTab, setActiveTab] = useState<"preview" | "html" | "text">("preview");
  const [editForm, setEditForm] = useState({
    title: "",
    content: "",
    plain_text: "",
    notes: "",
    brand_primary_color: "",
    brand_secondary_color: "",
  });

  useEffect(() => {
    if (id) loadProposal();
  }, [id]);

  async function loadProposal() {
    setLoading(true);
    try {
      const res = await proposalsApi.get(Number(id));
      const p = res.data;
      setProposal(p);
      setEditForm({
        title: p.title || "",
        content: p.content || "",
        plain_text: p.plain_text || "",
        notes: p.notes || "",
        brand_primary_color: p.brand_primary_color || "",
        brand_secondary_color: p.brand_secondary_color || "",
      });
      if (p.deal_id) {
        try {
          const d = await dealsApi.get(p.deal_id);
          setDeal(d.data);
        } catch {}
      }
    } catch (e: any) {
      setError(e.response?.data?.detail || "Error cargando propuesta");
    } finally {
      setLoading(false);
    }
  }

  async function handleSave() {
    if (!proposal) return;
    setSaving(true);
    try {
      await proposalsApi.update(proposal.id, {
        title: editForm.title,
        content: editForm.content,
        plain_text: editForm.plain_text,
        notes: editForm.notes,
        brand_primary_color: editForm.brand_primary_color,
        brand_secondary_color: editForm.brand_secondary_color,
      });
      loadProposal();
    } catch (e: any) {
      setError(e.response?.data?.detail || "Error guardando");
    } finally {
      setSaving(false);
    }
  }

  async function handleGenerate() {
    if (!proposal) return;
    setGenerating(true);
    try {
      await proposalsApi.generate(proposal.id);
      loadProposal();
    } catch (e: any) {
      setError(e.response?.data?.detail || "Error generando");
    } finally {
      setGenerating(false);
    }
  }

  async function handleSend() {
    if (!proposal) return;
    setSending(true);
    try {
      await proposalsApi.send(proposal.id);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
      loadProposal();
    } catch (e: any) {
      setError(e.response?.data?.detail || "Error enviando");
    } finally {
      setSending(false);
    }
  }

  async function copyPublicLink() {
    if (!proposal?.share_token) return;
    const url = `${window.location.origin}/proposals/public/${proposal.share_token}`;
    await navigator.clipboard.writeText(url);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
      </div>
    );
  }

  if (!proposal) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <FileText className="w-12 h-12 text-gray-300 mx-auto mb-3" />
          <p className="text-gray-500">Propuesta no encontrada</p>
        </div>
      </div>
    );
  }

  const publicUrl = proposal.share_token
    ? `${typeof window !== "undefined" ? window.location.origin : ""}/proposals/public/${proposal.share_token}`
    : null;

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 py-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <button
              onClick={() => router.push("/proposals")}
              className="p-2 text-gray-500 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div>
              <h1 className="text-xl font-bold text-gray-900">
                {proposal.title}
              </h1>
              <p className="text-sm text-gray-500">
                {deal?.name || "Sin deal"} · ${deal?.value?.toLocaleString() || 0} ·{" "}
                <span className="capitalize">{proposal.status}</span>
                {proposal.views_count ? ` · ${proposal.views_count} vistas` : ""}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {proposal.status === "draft" && (
              <>
                <button
                  onClick={handleGenerate}
                  disabled={generating}
                  className="flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50"
                >
                  {generating ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Wand2 className="w-4 h-4" />
                  )}
                  Generar con IA
                </button>
                <button
                  onClick={handleSend}
                  disabled={sending}
                  className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                >
                  {sending ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Send className="w-4 h-4" />
                  )}
                  Enviar
                </button>
              </>
            )}
            {proposal.status === "sent" && publicUrl && (
              <button
                onClick={copyPublicLink}
                className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700"
              >
                {copied ? (
                  <CheckCircle className="w-4 h-4" />
                ) : (
                  <Copy className="w-4 h-4" />
                )}
                {copied ? "Copiado" : "Copiar Link"}
              </button>
            )}
            <button
              onClick={handleSave}
              disabled={saving}
              className="flex items-center gap-2 px-4 py-2 bg-gray-900 text-white rounded-lg hover:bg-gray-800 disabled:opacity-50"
            >
              {saving ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Save className="w-4 h-4" />
              )}
              Guardar
            </button>
          </div>
        </div>

        {/* Error */}
        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2 text-red-700 text-sm">
            <AlertCircle className="w-4 h-4" />
            {error}
          </div>
        )}

        {/* Public link */}
        {publicUrl && (
          <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-lg flex items-center gap-2">
            <ExternalLink className="w-4 h-4 text-green-600" />
            <a
              href={publicUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-green-700 text-sm hover:underline truncate"
            >
              {publicUrl}
            </a>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left: Form */}
          <div className="lg:col-span-1 space-y-4">
            <div className="bg-white rounded-xl border border-gray-200 p-4">
              <h3 className="font-semibold text-gray-900 mb-3">Detalles</h3>
              <div className="space-y-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Título
                  </label>
                  <input
                    type="text"
                    value={editForm.title}
                    onChange={(e) =>
                      setEditForm({ ...editForm, title: e.target.value })
                    }
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Color Primario
                  </label>
                  <div className="flex items-center gap-2">
                    <input
                      type="color"
                      value={editForm.brand_primary_color || "#3b82f6"}
                      onChange={(e) =>
                        setEditForm({
                          ...editForm,
                          brand_primary_color: e.target.value,
                        })
                      }
                      className="w-10 h-10 rounded-lg border border-gray-200 cursor-pointer"
                    />
                    <input
                      type="text"
                      value={editForm.brand_primary_color || ""}
                      onChange={(e) =>
                        setEditForm({
                          ...editForm,
                          brand_primary_color: e.target.value,
                        })
                      }
                      className="flex-1 px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 text-sm"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Color Secundario
                  </label>
                  <div className="flex items-center gap-2">
                    <input
                      type="color"
                      value={editForm.brand_secondary_color || "#1e40af"}
                      onChange={(e) =>
                        setEditForm({
                          ...editForm,
                          brand_secondary_color: e.target.value,
                        })
                      }
                      className="w-10 h-10 rounded-lg border border-gray-200 cursor-pointer"
                    />
                    <input
                      type="text"
                      value={editForm.brand_secondary_color || ""}
                      onChange={(e) =>
                        setEditForm({
                          ...editForm,
                          brand_secondary_color: e.target.value,
                        })
                      }
                      className="flex-1 px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 text-sm"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Notas
                  </label>
                  <textarea
                    value={editForm.notes}
                    onChange={(e) =>
                      setEditForm({ ...editForm, notes: e.target.value })
                    }
                    rows={3}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 text-sm"
                  />
                </div>
              </div>
            </div>

            {deal && (
              <div className="bg-white rounded-xl border border-gray-200 p-4">
                <h3 className="font-semibold text-gray-900 mb-2">Deal</h3>
                <p className="text-sm text-gray-700">{deal.name}</p>
                <p className="text-sm text-gray-500">
                  ${deal.value?.toLocaleString() || 0} · {deal.status}
                </p>
              </div>
            )}
          </div>

          {/* Right: Preview */}
          <div className="lg:col-span-2">
            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              <div className="flex border-b border-gray-200">
                {(["preview", "html", "text"] as const).map((tab) => (
                  <button
                    key={tab}
                    onClick={() => setActiveTab(tab)}
                    className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                      activeTab === tab
                        ? "border-blue-600 text-blue-600"
                        : "border-transparent text-gray-500 hover:text-gray-700"
                    }`}
                  >
                    {tab === "preview"
                      ? "Vista Previa"
                      : tab === "html"
                      ? "HTML"
                      : "Texto"}
                  </button>
                ))}
              </div>

              <div className="p-4">
                {activeTab === "preview" && (
                  <div className="border border-gray-200 rounded-lg overflow-hidden">
                    {editForm.content ? (
                      <iframe
                        srcDoc={editForm.content}
                        className="w-full min-h-[600px]"
                        sandbox="allow-scripts"
                        title="Proposal Preview"
                      />
                    ) : (
                      <div className="flex items-center justify-center py-24 text-gray-400">
                        <div className="text-center">
                          <FileText className="w-12 h-12 mx-auto mb-2" />
                          <p>Sin contenido. Genera la propuesta con IA.</p>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {activeTab === "html" && (
                  <textarea
                    value={editForm.content}
                    onChange={(e) =>
                      setEditForm({ ...editForm, content: e.target.value })
                    }
                    className="w-full h-[600px] px-3 py-2 border border-gray-200 rounded-lg font-mono text-xs focus:ring-2 focus:ring-blue-500"
                  />
                )}

                {activeTab === "text" && (
                  <textarea
                    value={editForm.plain_text}
                    onChange={(e) =>
                      setEditForm({ ...editForm, plain_text: e.target.value })
                    }
                    className="w-full h-[600px] px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500"
                  />
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
