"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import {
  Play,
  Loader2,
  CheckCircle,
  XCircle,
  AlertTriangle,
  RefreshCw,
  Terminal,
  FileText,
  Clapperboard,
  Upload,
  Share2,
  ChevronDown,
  ChevronUp,
  Clock,
  Plus,
  Trash2,
  X,
  Sparkles,
  Globe,
} from "lucide-react";

interface Brief {
  filename: string;
  business_name: string;
  industry: string;
  city: string;
}

interface HealthStatus {
  status: string;
  message?: string;
}

interface Job {
  job_id: string;
  status: string;
  brief: string;
  stages: Record<string, boolean>;
  started_at: string;
  completed_at?: string;
  error?: string;
}

const PIPELINE_API_URL = "http://100.88.47.99:8002";

const STAGES = [
  { key: "content", label: "Content", description: "Generar guiones", icon: FileText },
  { key: "produce", label: "Produce", description: "Producir videos", icon: Clapperboard },
  { key: "upload", label: "Upload", description: "Subir a cloud", icon: Upload },
  { key: "publish", label: "Publish", description: "Publicar en redes", icon: Share2 },
];

const SERVICE_LABELS: Record<string, string> = {
  buffer: "Buffer",
  elevenlabs: "ElevenLabs TTS",
  huggingface: "Hugging Face",
  minimax: "MiniMax Hailuo",
};

export default function RunPipelinePanel() {
  const [health, setHealth] = useState<Record<string, HealthStatus>>({});
  const [briefs, setBriefs] = useState<Brief[]>([]);
  const [selectedBrief, setSelectedBrief] = useState("");
  const [selectedStages, setSelectedStages] = useState<Record<string, boolean>>({
    content: true,
    produce: false,
    upload: false,
    publish: false,
  });
  const [jobs, setJobs] = useState<Job[]>([]);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [activeJobLogs, setActiveJobLogs] = useState<string[]>([]);
  const [running, setRunning] = useState(false);
  const [loadingHealth, setLoadingHealth] = useState(true);
  const [loadingBriefs, setLoadingBriefs] = useState(true);
  const [expandedJob, setExpandedJob] = useState<string | null>(null);
  const [showNewBrief, setShowNewBrief] = useState(false);
  const [templates, setTemplates] = useState<Record<string, string>>({});
  const logsEndRef = useRef<HTMLDivElement>(null);

  const fetchHealth = useCallback(async () => {
    try {
      const res = await fetch(`${PIPELINE_API_URL}/health`);
      const data = await res.json();
      setHealth(data);
    } catch {
      setHealth({});
    } finally {
      setLoadingHealth(false);
    }
  }, []);

  const fetchBriefs = useCallback(async () => {
    try {
      const res = await fetch(`${PIPELINE_API_URL}/briefs`);
      const data = await res.json();
      setBriefs(data.briefs || []);
      if (data.briefs?.length > 0 && !selectedBrief) {
        setSelectedBrief(data.briefs[0].filename);
      }
    } catch {
      setBriefs([]);
    } finally {
      setLoadingBriefs(false);
    }
  }, [selectedBrief]);

  const fetchTemplates = useCallback(async () => {
    try {
      const res = await fetch(`${PIPELINE_API_URL}/briefs/templates`);
      const data = await res.json();
      setTemplates(data.templates || {});
    } catch {
      setTemplates({});
    }
  }, []);

  const fetchJobs = useCallback(async () => {
    try {
      const res = await fetch(`${PIPELINE_API_URL}/jobs`);
      const data = await res.json();
      setJobs(data.jobs || []);
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    fetchHealth();
    fetchBriefs();
    fetchJobs();
    fetchTemplates();
    const interval = setInterval(() => {
      fetchHealth();
      fetchJobs();
    }, 10000);
    return () => clearInterval(interval);
  }, [fetchHealth, fetchBriefs, fetchJobs, fetchTemplates]);

  // Poll active job logs
  useEffect(() => {
    if (!activeJobId) return;
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${PIPELINE_API_URL}/jobs/${activeJobId}`);
        const data = await res.json();
        setActiveJobLogs(data.logs || []);
        if (data.status === "completed" || data.status === "failed") {
          setRunning(false);
          fetchJobs();
        }
      } catch {
        // ignore
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [activeJobId, fetchJobs]);

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [activeJobLogs]);

  const handleRun = async () => {
    if (!selectedBrief) return;
    setRunning(true);
    setActiveJobLogs([]);
    try {
      const res = await fetch(`${PIPELINE_API_URL}/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          brief: selectedBrief,
          ...selectedStages,
        }),
      });
      const data = await res.json();
      if (data.job_id) {
        setActiveJobId(data.job_id);
      } else {
        setRunning(false);
      }
    } catch {
      setRunning(false);
    }
  };

  const toggleStage = (key: string) => {
    setSelectedStages((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const statusIcon = (status: string) => {
    switch (status) {
      case "ok":
        return <CheckCircle className="w-4 h-4 text-eko-green" />;
      case "rate_limited":
        return <AlertTriangle className="w-4 h-4 text-yellow-400" />;
      case "error":
        return <XCircle className="w-4 h-4 text-red-400" />;
      default:
        return <XCircle className="w-4 h-4 text-gray-500" />;
    }
  };

  const statusLabel = (status: string) => {
    switch (status) {
      case "ok":
        return "Activo";
      case "rate_limited":
        return "Rate limit";
      case "error":
        return "Error";
      default:
        return "Desconocido";
    }
  };

  return (
    <>
    <div className="space-y-6">
      {/* API Health */}
      <div className="rounded-xl border border-white/5 bg-white/[0.02] p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-medium text-gray-400">
            Estado de APIs
          </h3>
          <button
            onClick={fetchHealth}
            className="p-1 rounded-lg text-gray-400 hover:text-white hover:bg-white/10 transition-colors"
            title="Refrescar"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>
        {loadingHealth ? (
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <Loader2 className="w-4 h-4 animate-spin" />
            Verificando...
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {Object.entries(health).map(([key, value]) => (
              <div
                key={key}
                className="rounded-lg bg-white/5 p-3 flex items-center gap-2"
              >
                {statusIcon(value.status)}
                <div>
                  <p className="text-xs font-medium text-gray-300">
                    {SERVICE_LABELS[key] || key}
                  </p>
                  <p className="text-[10px] text-gray-500">
                    {statusLabel(value.status)}
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Run Pipeline */}
      <div className="rounded-xl border border-white/5 bg-white/[0.02] p-4">
        <h3 className="text-sm font-medium text-gray-400 mb-4">
          Ejecutar Pipeline
        </h3>

        {/* Brief selector */}
        <div className="mb-4">
          <div className="flex items-center justify-between mb-1.5">
            <label className="text-xs text-gray-500">Brief</label>
            <button
              onClick={() => setShowNewBrief(true)}
              className="flex items-center gap-1 px-2 py-1 rounded-lg text-[11px] font-medium text-pink-400 hover:bg-pink-500/10 border border-pink-500/20 transition-colors"
            >
              <Plus className="w-3 h-3" />
              Nuevo cliente
            </button>
          </div>
          {loadingBriefs ? (
            <div className="flex items-center gap-2 text-sm text-gray-500">
              <Loader2 className="w-4 h-4 animate-spin" />
              Cargando...
            </div>
          ) : briefs.length === 0 ? (
            <p className="text-sm text-gray-500">No hay briefs. Crea uno con "Nuevo cliente".</p>
          ) : (
            <div className="flex gap-2">
              <select
                value={selectedBrief}
                onChange={(e) => setSelectedBrief(e.target.value)}
                className="flex-1 rounded-lg bg-white/5 border border-white/10 px-3 py-2 text-sm text-gray-300 focus:outline-none focus:border-pink-400/50"
              >
                {briefs.map((b) => (
                  <option key={b.filename} value={b.filename}>
                    {b.business_name} ({b.city}) — {b.industry}
                  </option>
                ))}
              </select>
              {selectedBrief && selectedBrief !== "brief_cafe_eko.json" && (
                <button
                  onClick={async () => {
                    if (!confirm(`¿Eliminar el brief "${selectedBrief}"?`)) return;
                    await fetch(`${PIPELINE_API_URL}/briefs/${selectedBrief}`, { method: "DELETE" });
                    setSelectedBrief("");
                    fetchBriefs();
                  }}
                  className="p-2 rounded-lg text-gray-500 hover:text-red-400 hover:bg-red-500/10 transition-colors border border-white/5"
                  title="Eliminar brief"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              )}
            </div>
          )}
        </div>

        {/* Stage toggles */}
        <div className="mb-4">
          <label className="text-xs text-gray-500 mb-1.5 block">Etapas</label>
          <div className="flex flex-wrap gap-2">
            {STAGES.map((stage) => {
              const Icon = stage.icon;
              const active = selectedStages[stage.key];
              return (
                <button
                  key={stage.key}
                  onClick={() => toggleStage(stage.key)}
                  disabled={running}
                  className={`flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium transition-colors border ${
                    active
                      ? "bg-pink-500/10 text-pink-400 border-pink-500/30"
                      : "bg-white/5 text-gray-400 border-white/5 hover:bg-white/10"
                  } ${running ? "opacity-50 cursor-not-allowed" : ""}`}
                >
                  <Icon className="w-3.5 h-3.5" />
                  <div className="text-left">
                    <div>{stage.label}</div>
                    <div className="text-[10px] text-gray-500">
                      {stage.description}
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Run button */}
        <div className="flex items-center gap-3">
          <button
            onClick={handleRun}
            disabled={running || !selectedBrief}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              running || !selectedBrief
                ? "bg-white/5 text-gray-500 cursor-not-allowed"
                : "bg-pink-500/20 text-pink-400 hover:bg-pink-500/30 border border-pink-500/30"
            }`}
          >
            {running ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Ejecutando...
              </>
            ) : (
              <>
                <Play className="w-4 h-4" />
                Ejecutar pipeline
              </>
            )}
          </button>
          {activeJobId && running && (
            <span className="text-xs text-gray-500">
              Job: {activeJobId.slice(0, 8)}...
            </span>
          )}
        </div>

        {/* Live logs */}
        {activeJobId && (
          <div className="mt-4">
            <div className="flex items-center gap-2 mb-2">
              <Terminal className="w-3.5 h-3.5 text-gray-400" />
              <span className="text-xs text-gray-400">Logs en tiempo real</span>
              {running && (
                <Loader2 className="w-3 h-3 animate-spin text-eko-blue" />
              )}
            </div>
            <div className="rounded-lg bg-black/40 border border-white/5 p-3 font-mono text-[11px] text-gray-300 h-64 overflow-y-auto">
              {activeJobLogs.length === 0 ? (
                <span className="text-gray-600">Esperando inicio...</span>
              ) : (
                activeJobLogs.map((line, i) => (
                  <div key={i} className="leading-relaxed">
                    {line}
                  </div>
                ))
              )}
              <div ref={logsEndRef} />
            </div>
          </div>
        )}
      </div>

      {/* Job History */}
      <div className="rounded-xl border border-white/5 bg-white/[0.02] p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-medium text-gray-400">
            Historial de ejecuciones
          </h3>
          <button
            onClick={fetchJobs}
            className="p-1 rounded-lg text-gray-400 hover:text-white hover:bg-white/10 transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>

        {jobs.length === 0 ? (
          <p className="text-sm text-gray-500">Sin ejecuciones recientes.</p>
        ) : (
          <div className="space-y-2">
            {jobs.map((job) => {
              const isExpanded = expandedJob === job.job_id;
              const isActive = activeJobId === job.job_id;
              const statusColor =
                job.status === "completed"
                  ? "text-eko-green"
                  : job.status === "failed"
                  ? "text-red-400"
                  : job.status === "running"
                  ? "text-eko-blue"
                  : "text-yellow-400";

              return (
                <div
                  key={job.job_id}
                  className={`rounded-lg border p-3 transition-colors ${
                    isActive
                      ? "bg-white/[0.04] border-pink-400/20"
                      : "bg-white/5 border-white/5"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className={`text-xs font-medium ${statusColor}`}>
                        {job.status === "completed"
                          ? "✓ Completado"
                          : job.status === "failed"
                          ? "✗ Fallido"
                          : job.status === "running"
                          ? "⟳ En ejecución"
                          : "⏳ Pendiente"}
                      </span>
                      <span className="text-[10px] text-gray-500">
                        {job.brief}
                      </span>
                    </div>
                    <div className="flex items-center gap-1">
                      <span className="text-[10px] text-gray-500">
                        {new Date(job.started_at).toLocaleString("es-CO", {
                          month: "short",
                          day: "numeric",
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </span>
                      <button
                        onClick={() =>
                          setExpandedJob(isExpanded ? null : job.job_id)
                        }
                        className="p-1 rounded text-gray-400 hover:text-white"
                      >
                        {isExpanded ? (
                          <ChevronUp className="w-3 h-3" />
                        ) : (
                          <ChevronDown className="w-3 h-3" />
                        )}
                      </button>
                    </div>
                  </div>

                  {isExpanded && (
                    <div className="mt-2 pt-2 border-t border-white/5">
                      <div className="text-[10px] text-gray-500 mb-1">
                        ID: {job.job_id}
                      </div>
                      <div className="text-[10px] text-gray-500 mb-2">
                        Etapas:{" "}
                        {Object.entries(job.stages || {})
                          .filter(([, v]) => v)
                          .map(([k]) => k)
                          .join(", ") || "content"}
                      </div>
                      {job.error && (
                        <div className="text-[10px] text-red-400 mb-2">
                          Error: {job.error}
                        </div>
                      )}
                      <JobLogs jobId={job.job_id} />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>

    {showNewBrief && (
      <NewBriefModal
        templates={templates}
        onClose={() => setShowNewBrief(false)}
        onCreated={(filename) => {
          setShowNewBrief(false);
          fetchBriefs();
          setSelectedBrief(filename);
        }}
      />
    )}
  </>
  );
}

const LANGUAGES: { code: string; label: string; flag: string }[] = [
  { code: "es", label: "Español", flag: "🇪🇸" },
  { code: "en", label: "English", flag: "🇺🇸" },
  { code: "pt", label: "Português", flag: "🇧🇷" },
  { code: "fr", label: "Français", flag: "🇫🇷" },
  { code: "de", label: "Deutsch", flag: "🇩🇪" },
  { code: "it", label: "Italiano", flag: "🇮🇹" },
  { code: "ja", label: "日本語", flag: "🇯🇵" },
  { code: "ko", label: "한국어", flag: "🇰🇷" },
  { code: "zh", label: "中文", flag: "🇨🇳" },
  { code: "ar", label: "العربية", flag: "🇸🇦" },
  { code: "ru", label: "Русский", flag: "🇷🇺" },
  { code: "hi", label: "हिन्दी", flag: "🇮🇳" },
];

function NewBriefModal({
  templates,
  onClose,
  onCreated,
}: {
  templates: Record<string, string>;
  onClose: () => void;
  onCreated: (filename: string) => void;
}) {
  const [form, setForm] = useState({
    business_name: "",
    industry: "restaurant",
    language: "es",
    city: "",
    address: "",
    description: "",
    products: "",
    unique_selling_points: "",
    target_audience: "",
    brand_tone: "",
    special_offers: "",
    price_range: "",
    hashtags: "",
    origin_story: "",
    surprising_fact: "",
    key_benefit: "",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const [websiteUrl, setWebsiteUrl] = useState("");
  const [extracting, setExtracting] = useState(false);
  const [extractError, setExtractError] = useState("");
  const [extractProgress, setExtractProgress] = useState(0);
  const [extractStep, setExtractStep] = useState("");

  const set = (k: string, v: string) => setForm((f) => ({ ...f, [k]: v }));

  const splitLines = (s: string) => s.split("\n").map((l) => l.trim()).filter(Boolean);
  const joinLines = (arr: any) => Array.isArray(arr) ? arr.join("\n") : (arr || "");

  const handleExtract = async () => {
    const url = websiteUrl.trim();
    if (!url) {
      setExtractError("Ingresa una URL primero.");
      return;
    }
    setExtractError("");
    setExtracting(true);
    setExtractProgress(5);
    setExtractStep("Descargando página web...");

    const timers: ReturnType<typeof setTimeout>[] = [];
    timers.push(setTimeout(() => { setExtractProgress(30); setExtractStep("Analizando contenido con IA..."); }, 2000));
    timers.push(setTimeout(() => { setExtractProgress(60); setExtractStep("Extrayendo datos del negocio..."); }, 7000));
    timers.push(setTimeout(() => { setExtractProgress(85); }, 14000));

    try {
      const res = await fetch(`${PIPELINE_API_URL}/briefs/extract`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      });
      const data = await res.json();
      if (!res.ok || data.detail) {
        throw new Error(data.detail || `HTTP ${res.status}`);
      }
      timers.forEach(clearTimeout);
      setExtractProgress(100);
      setExtractStep("Llenando campos...");
      setForm((f) => ({
        ...f,
        business_name: data.business_name || f.business_name,
        industry: data.industry || f.industry,
        language: data.language || f.language,
        city: data.city || f.city,
        address: data.address || f.address,
        description: data.description || f.description,
        products: joinLines(data.products) || f.products,
        unique_selling_points: joinLines(data.unique_selling_points) || f.unique_selling_points,
        target_audience: data.target_audience || f.target_audience,
        brand_tone: data.brand_tone || f.brand_tone,
        special_offers: joinLines(data.special_offers) || f.special_offers,
        price_range: data.price_range || f.price_range,
        hashtags: joinLines(data.hashtags) || f.hashtags,
        origin_story: data.origin_story || f.origin_story,
        surprising_fact: data.surprising_fact || f.surprising_fact,
        key_benefit: data.key_benefit || f.key_benefit,
      }));
      setTimeout(() => {
        setExtracting(false);
        setExtractProgress(0);
        setExtractStep("");
      }, 800);
    } catch (e: any) {
      timers.forEach(clearTimeout);
      setExtractError(e.message || "Error al extraer información");
      setExtracting(false);
      setExtractProgress(0);
      setExtractStep("");
    }
  };

  const handleSubmit = async () => {
    if (!form.business_name.trim() || !form.city.trim()) {
      setError("Nombre de negocio y ciudad son obligatorios.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const res = await fetch(`${PIPELINE_API_URL}/briefs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...form,
          products: splitLines(form.products),
          unique_selling_points: splitLines(form.unique_selling_points),
          special_offers: splitLines(form.special_offers),
          hashtags: splitLines(form.hashtags),
          testimonials: [],
        }),
      });
      const data = await res.json();
      if (data.detail) throw new Error(data.detail);
      onCreated(data.filename);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="w-full max-w-2xl rounded-xl border border-white/10 bg-eko-graphite shadow-2xl flex flex-col max-h-[90vh]">
        <div className="flex items-center justify-between px-5 py-3 border-b border-white/5">
          <h3 className="text-sm font-medium">Nuevo cliente / Brief</h3>
          <button onClick={onClose} className="p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-white/10 transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-5 overflow-y-auto space-y-4 flex-1">
          {/* AI Extract from URL */}
          <div className="rounded-lg border border-pink-500/20 bg-gradient-to-br from-pink-500/[0.04] to-purple-500/[0.04] p-3">
            <div className="flex items-center gap-2 mb-2">
              <Sparkles className="w-3.5 h-3.5 text-pink-400" />
              <label className="text-[11px] font-medium text-pink-300">
                Auto-llenar desde página web
              </label>
            </div>
            <div className="flex gap-2">
              <div className="flex-1 relative">
                <Globe className="w-3.5 h-3.5 text-gray-500 absolute left-2.5 top-1/2 -translate-y-1/2" />
                <input
                  type="url"
                  value={websiteUrl}
                  onChange={(e) => setWebsiteUrl(e.target.value)}
                  disabled={extracting}
                  placeholder="https://www.tunegocio.com"
                  className="w-full rounded-lg bg-white/5 border border-white/10 pl-8 pr-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-pink-400/50 disabled:opacity-50"
                  onKeyDown={(e) => { if (e.key === "Enter" && !extracting) { e.preventDefault(); handleExtract(); } }}
                />
              </div>
              <button
                onClick={handleExtract}
                disabled={extracting || !websiteUrl.trim()}
                className="flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium bg-pink-500/20 text-pink-400 hover:bg-pink-500/30 border border-pink-500/30 transition-colors disabled:opacity-40 disabled:cursor-not-allowed whitespace-nowrap"
              >
                {extracting ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    Procesando...
                  </>
                ) : (
                  <>
                    <Sparkles className="w-3.5 h-3.5" />
                    Procesar con IA
                  </>
                )}
              </button>
            </div>

            {/* Progress bar */}
            {extracting && (
              <div className="mt-3">
                <div className="rounded-full bg-white/5 h-1.5 overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-pink-400 to-purple-400 transition-all duration-700 ease-out"
                    style={{ width: `${extractProgress}%` }}
                  />
                </div>
                <p className="text-[10px] text-gray-400 mt-1.5 flex items-center gap-1.5">
                  <Loader2 className="w-2.5 h-2.5 animate-spin" />
                  {extractStep}
                </p>
              </div>
            )}

            {!extracting && !extractError && (
              <p className="text-[10px] text-gray-500 mt-2">
                La IA descargará la página y llenará todos los campos automáticamente. Después puedes editar lo que necesites.
              </p>
            )}

            {extractError && (
              <p className="text-[10px] text-red-400 mt-2 flex items-center gap-1">
                <AlertTriangle className="w-3 h-3" />
                {extractError}
              </p>
            )}
          </div>

          {/* Row: name + industry + language */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div>
              <label className="text-[11px] text-gray-500 mb-1 block">Nombre del negocio *</label>
              <input
                value={form.business_name}
                onChange={(e) => set("business_name", e.target.value)}
                placeholder="Ej: Café EKO"
                className="w-full rounded-lg bg-white/5 border border-white/10 px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-pink-400/50"
              />
            </div>
            <div>
              <label className="text-[11px] text-gray-500 mb-1 block">Industria</label>
              <select
                value={form.industry}
                onChange={(e) => set("industry", e.target.value)}
                className="w-full rounded-lg bg-white/5 border border-white/10 px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-pink-400/50"
              >
                {Object.entries(templates).map(([k, v]) => (
                  <option key={k} value={k}>{v}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-[11px] text-gray-500 mb-1 block flex items-center gap-1">
                Idioma de la publicidad
              </label>
              <select
                value={form.language}
                onChange={(e) => set("language", e.target.value)}
                className="w-full rounded-lg bg-white/5 border border-white/10 px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-pink-400/50"
                title="Idioma en que se generarán los videos, guiones y captions"
              >
                {LANGUAGES.map((l) => (
                  <option key={l.code} value={l.code}>
                    {l.flag} {l.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Row: city + address */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[11px] text-gray-500 mb-1 block">Ciudad *</label>
              <input
                value={form.city}
                onChange={(e) => set("city", e.target.value)}
                placeholder="Ej: Bogotá"
                className="w-full rounded-lg bg-white/5 border border-white/10 px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-pink-400/50"
              />
            </div>
            <div>
              <label className="text-[11px] text-gray-500 mb-1 block">Dirección / Zona</label>
              <input
                value={form.address}
                onChange={(e) => set("address", e.target.value)}
                placeholder="Ej: Zona G, Chapinero"
                className="w-full rounded-lg bg-white/5 border border-white/10 px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-pink-400/50"
              />
            </div>
          </div>

          {/* Description */}
          <div>
            <label className="text-[11px] text-gray-500 mb-1 block">Descripción del negocio</label>
            <textarea
              value={form.description}
              onChange={(e) => set("description", e.target.value)}
              placeholder="Qué hace el negocio, qué lo hace especial..."
              rows={2}
              className="w-full rounded-lg bg-white/5 border border-white/10 px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-pink-400/50 resize-none"
            />
          </div>

          {/* Products + USPs */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[11px] text-gray-500 mb-1 block">Productos / Servicios <span className="text-gray-600">(uno por línea)</span></label>
              <textarea
                value={form.products}
                onChange={(e) => set("products", e.target.value)}
                placeholder={"café de origen\nbrunch artesanal\npostres caseros"}
                rows={3}
                className="w-full rounded-lg bg-white/5 border border-white/10 px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-pink-400/50 resize-none"
              />
            </div>
            <div>
              <label className="text-[11px] text-gray-500 mb-1 block">Propuestas de valor <span className="text-gray-600">(uno por línea)</span></label>
              <textarea
                value={form.unique_selling_points}
                onChange={(e) => set("unique_selling_points", e.target.value)}
                placeholder={"granos de finca local\npan horneado a diario\nWiFi rápido"}
                rows={3}
                className="w-full rounded-lg bg-white/5 border border-white/10 px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-pink-400/50 resize-none"
              />
            </div>
          </div>

          {/* Audience + tone + price */}
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="text-[11px] text-gray-500 mb-1 block">Audiencia objetivo</label>
              <input
                value={form.target_audience}
                onChange={(e) => set("target_audience", e.target.value)}
                placeholder="Ej: jóvenes 25-35"
                className="w-full rounded-lg bg-white/5 border border-white/10 px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-pink-400/50"
              />
            </div>
            <div>
              <label className="text-[11px] text-gray-500 mb-1 block">Tono de marca</label>
              <input
                value={form.brand_tone}
                onChange={(e) => set("brand_tone", e.target.value)}
                placeholder="Ej: cálido, cercano"
                className="w-full rounded-lg bg-white/5 border border-white/10 px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-pink-400/50"
              />
            </div>
            <div>
              <label className="text-[11px] text-gray-500 mb-1 block">Rango de precios</label>
              <input
                value={form.price_range}
                onChange={(e) => set("price_range", e.target.value)}
                placeholder="Ej: $8.000–$25.000 COP"
                className="w-full rounded-lg bg-white/5 border border-white/10 px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-pink-400/50"
              />
            </div>
          </div>

          {/* Special offers + hashtags */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[11px] text-gray-500 mb-1 block">Ofertas especiales <span className="text-gray-600">(uno por línea)</span></label>
              <textarea
                value={form.special_offers}
                onChange={(e) => set("special_offers", e.target.value)}
                placeholder={"happy hour 4-6pm\ncafé + pan $8.000"}
                rows={2}
                className="w-full rounded-lg bg-white/5 border border-white/10 px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-pink-400/50 resize-none"
              />
            </div>
            <div>
              <label className="text-[11px] text-gray-500 mb-1 block">Hashtags <span className="text-gray-600">(uno por línea)</span></label>
              <textarea
                value={form.hashtags}
                onChange={(e) => set("hashtags", e.target.value)}
                placeholder={"#cafébogotá\n#brunchbogotá"}
                rows={2}
                className="w-full rounded-lg bg-white/5 border border-white/10 px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-pink-400/50 resize-none"
              />
            </div>
          </div>

          {/* Origin + key benefit */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[11px] text-gray-500 mb-1 block">Historia de origen</label>
              <textarea
                value={form.origin_story}
                onChange={(e) => set("origin_story", e.target.value)}
                placeholder="¿Cómo empezó el negocio?"
                rows={2}
                className="w-full rounded-lg bg-white/5 border border-white/10 px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-pink-400/50 resize-none"
              />
            </div>
            <div>
              <label className="text-[11px] text-gray-500 mb-1 block">Dato sorprendente</label>
              <input
                value={form.surprising_fact}
                onChange={(e) => set("surprising_fact", e.target.value)}
                placeholder="Ej: tostamos granos cada semana"
                className="w-full rounded-lg bg-white/5 border border-white/10 px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-pink-400/50"
              />
            </div>
          </div>

          {error && (
            <div className="rounded-lg border border-red-500/20 bg-red-500/5 p-3 text-red-400 text-xs">
              {error}
            </div>
          )}
        </div>

        <div className="px-5 py-3 border-t border-white/5 flex items-center justify-end gap-2">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg text-sm text-gray-400 hover:text-white hover:bg-white/10 transition-colors"
          >
            Cancelar
          </button>
          <button
            onClick={handleSubmit}
            disabled={saving}
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-pink-500/20 text-pink-400 hover:bg-pink-500/30 border border-pink-500/30 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
            Crear brief
          </button>
        </div>
      </div>
    </div>
  );
}

function JobLogs({ jobId }: { jobId: string }) {
  const [logs, setLogs] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${PIPELINE_API_URL}/jobs/${jobId}`)
      .then((r) => r.json())
      .then((data) => {
        setLogs(data.logs || []);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [jobId]);

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-[10px] text-gray-500">
        <Loader2 className="w-3 h-3 animate-spin" />
        Cargando logs...
      </div>
    );
  }

  return (
    <div className="rounded bg-black/30 p-2 font-mono text-[10px] text-gray-400 max-h-40 overflow-y-auto">
      {logs.length === 0 ? (
        <span className="text-gray-600">Sin logs.</span>
      ) : (
        logs.slice(-50).map((line, i) => (
          <div key={i} className="leading-relaxed">
            {line}
          </div>
        ))
      )}
    </div>
  );
}
