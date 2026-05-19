"use client";

import { useEffect, useState } from "react";
import {
  CheckCircle,
  XCircle,
  Clock,
  Loader2,
  PlayCircle,
  RefreshCw,
} from "lucide-react";

interface Pipeline {
  filename: string;
  started_at: string;
  business_name: string;
  stages: Record<string, { status?: string; scripts?: any[]; produced?: any[]; uploaded?: any[]; published?: any[] }>;
  paperclip_issue_id?: string;
}

function inferStatus(stage: Pipeline["stages"][string] | undefined): string {
  if (!stage) return "missing";
  if (stage.status) return stage.status;
  // Infer from arrays present in the stage payload
  const hasData =
    (stage.scripts?.length || 0) > 0 ||
    (stage.produced?.length || 0) > 0 ||
    (stage.uploaded?.length || 0) > 0 ||
    (stage.published?.length || 0) > 0;
  return hasData ? "completed" : "pending";
}

const STATUS_LABEL: Record<string, string> = {
  completed: "Completado",
  failed: "Falló",
  running: "En curso",
  pending: "Pendiente",
  missing: "—",
};

export default function PipelineHistory() {
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = () => {
    setLoading(true);
    fetch("/content-api/pipelines")
      .then((r) => r.json())
      .then((data) => {
        if (data.error) throw new Error(data.error);
        setPipelines(data.pipelines || []);
        setError("");
      })
      .catch((e) => setError(e.message || "Error cargando pipelines"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, []);

  if (loading && pipelines.length === 0) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-6 h-6 animate-spin text-eko-blue" />
      </div>
    );
  }

  const statusIcon = (status: string) => {
    if (status === "completed")
      return <CheckCircle className="w-4 h-4 text-eko-green" />;
    if (status === "failed")
      return <XCircle className="w-4 h-4 text-red-500" />;
    if (status === "running")
      return <PlayCircle className="w-4 h-4 text-eko-blue animate-pulse" />;
    if (status === "pending")
      return <Clock className="w-4 h-4 text-yellow-400" />;
    return <Clock className="w-4 h-4 text-gray-500" />;
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-end">
        <button
          onClick={load}
          disabled={loading}
          className="p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-white/10 transition-colors disabled:opacity-50"
          title="Refrescar"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
        </button>
      </div>

      {error && (
        <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-3 text-red-400 text-sm">
          {error}
        </div>
      )}

      <div className="rounded-xl border border-white/5 bg-white/[0.02] overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-white/5 text-left text-gray-500">
              <th className="px-4 py-3 font-medium">Fecha</th>
              <th className="px-4 py-3 font-medium">Negocio</th>
              <th className="px-4 py-3 font-medium">Content</th>
              <th className="px-4 py-3 font-medium">Produce</th>
              <th className="px-4 py-3 font-medium">Upload</th>
              <th className="px-4 py-3 font-medium">Publish</th>
              <th className="px-4 py-3 font-medium">Paperclip</th>
            </tr>
          </thead>
          <tbody>
            {pipelines.map((p) => (
              <tr
                key={p.filename}
                className="border-b border-white/5 hover:bg-white/[0.02] transition-colors"
              >
                <td className="px-4 py-3 text-gray-400">
                  {p.started_at
                    ? new Date(p.started_at).toLocaleString("es-CO", {
                        month: "short",
                        day: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                      })
                    : "—"}
                </td>
                <td className="px-4 py-3 font-medium">
                  {p.business_name || "—"}
                </td>
                {["content", "produce", "upload", "publish"].map((stage) => {
                  const status = inferStatus(p.stages?.[stage]);
                  return (
                    <td key={stage} className="px-4 py-3">
                      <div className="flex items-center gap-1.5">
                        {statusIcon(status)}
                        <span className="text-gray-400 capitalize text-xs">
                          {STATUS_LABEL[status] || status}
                        </span>
                      </div>
                    </td>
                  );
                })}
                <td className="px-4 py-3 text-gray-500">
                  {p.paperclip_issue_id ? (
                    <span
                      className="font-mono text-xs"
                      title={p.paperclip_issue_id}
                    >
                      {p.paperclip_issue_id.slice(0, 8)}...
                    </span>
                  ) : (
                    "—"
                  )}
                </td>
              </tr>
            ))}
            {pipelines.length === 0 && !loading && (
              <tr>
                <td
                  colSpan={7}
                  className="px-4 py-8 text-center text-gray-500"
                >
                  No hay pipelines ejecutados aún.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
