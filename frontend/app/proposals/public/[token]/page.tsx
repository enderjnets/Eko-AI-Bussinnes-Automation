"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import axios from "axios";
import {
  CheckCircle,
  XCircle,
  Loader2,
  AlertCircle,
  FileText,
  Building2,
  DollarSign,
} from "lucide-react";

interface PublicProposal {
  id: number;
  title: string;
  content: string;
  brand_primary_color: string | null;
  brand_secondary_color: string | null;
  brand_logo_url: string | null;
  deal_name: string | null;
  deal_value: number | null;
  business_name: string | null;
  status: string;
  created_at: string;
}

export default function PublicProposalPage() {
  const { token } = useParams();
  const [proposal, setProposal] = useState<PublicProposal | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionLoading, setActionLoading] = useState(false);
  const [actionResult, setActionResult] = useState<"accepted" | "rejected" | null>(null);
  const [feedback, setFeedback] = useState("");

  useEffect(() => {
    if (token) loadProposal();
  }, [token]);

  async function loadProposal() {
    setLoading(true);
    try {
      // Public endpoint doesn't need auth
      const res = await axios.get(
        `${process.env.NEXT_PUBLIC_API_URL || ""}/api/v1/proposals/public/${token}`
      );
      setProposal(res.data);
    } catch (e: any) {
      setError(e.response?.data?.detail || "Propuesta no encontrada");
    } finally {
      setLoading(false);
    }
  }

  async function handleAccept() {
    if (!token) return;
    setActionLoading(true);
    try {
      await axios.post(
        `${process.env.NEXT_PUBLIC_API_URL || ""}/api/v1/proposals/public/${token}/accept`
      );
      setActionResult("accepted");
    } catch (e: any) {
      setError(e.response?.data?.detail || "Error aceptando propuesta");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleReject() {
    if (!token) return;
    setActionLoading(true);
    try {
      await axios.post(
        `${process.env.NEXT_PUBLIC_API_URL || ""}/api/v1/proposals/public/${token}/reject`,
        null,
        { params: { feedback } }
      );
      setActionResult("rejected");
    } catch (e: any) {
      setError(e.response?.data?.detail || "Error rechazando propuesta");
    } finally {
      setActionLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center max-w-md mx-auto px-4">
          <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-3" />
          <h2 className="text-lg font-semibold text-gray-900 mb-1">
            Propuesta no disponible
          </h2>
          <p className="text-gray-500">{error}</p>
        </div>
      </div>
    );
  }

  if (!proposal) return null;

  if (actionResult === "accepted") {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center max-w-md mx-auto px-4">
          <CheckCircle className="w-16 h-16 text-green-500 mx-auto mb-4" />
          <h2 className="text-2xl font-bold text-gray-900 mb-2">
            ¡Propuesta Aceptada!
          </h2>
          <p className="text-gray-600 mb-4">
            Gracias por aceptar la propuesta. Nos pondremos en contacto contigo
            pronto para los siguientes pasos.
          </p>
          <p className="text-sm text-gray-400">
            {proposal.business_name || ""}
          </p>
        </div>
      </div>
    );
  }

  if (actionResult === "rejected") {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center max-w-md mx-auto px-4">
          <XCircle className="w-16 h-16 text-red-400 mx-auto mb-4" />
          <h2 className="text-2xl font-bold text-gray-900 mb-2">
            Propuesta Rechazada
          </h2>
          <p className="text-gray-600 mb-4">
            Gracias por tu tiempo. Si cambias de opinión, no dudes en
            contactarnos.
          </p>
          <p className="text-sm text-gray-400">
            {proposal.business_name || ""}
          </p>
        </div>
      </div>
    );
  }

  const isActionable = proposal.status === "sent";

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header bar */}
      <div
        className="py-4 px-4"
        style={{
          backgroundColor: proposal.brand_primary_color || "#3b82f6",
        }}
      >
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            {proposal.brand_logo_url ? (
              <img
                src={proposal.brand_logo_url}
                alt="Logo"
                className="w-8 h-8 object-contain rounded"
              />
            ) : (
              <Building2 className="w-6 h-6 text-white" />
            )}
            <div>
              <h1 className="text-white font-semibold text-lg">
                {proposal.business_name || "Propuesta"}
              </h1>
              <p className="text-white/80 text-sm">
                {proposal.deal_name || proposal.title}
              </p>
            </div>
          </div>
          {proposal.deal_value ? (
            <div className="text-right">
              <p className="text-white/80 text-xs">Valor estimado</p>
              <p className="text-white font-bold text-xl">
                ${proposal.deal_value.toLocaleString()}
              </p>
            </div>
          ) : null}
        </div>
      </div>

      {/* Proposal Content */}
      <div className="max-w-4xl mx-auto px-4 py-8">
        {proposal.content ? (
          <div
            className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden"
            dangerouslySetInnerHTML={{ __html: proposal.content }}
          />
        ) : (
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-12 text-center">
            <FileText className="w-12 h-12 text-gray-300 mx-auto mb-3" />
            <p className="text-gray-500">El contenido de la propuesta no está disponible.</p>
          </div>
        )}

        {/* Action Buttons */}
        {isActionable && (
          <div className="mt-8 bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">
              ¿Qué decides?
            </h3>
            <div className="flex flex-col sm:flex-row gap-3">
              <button
                onClick={handleAccept}
                disabled={actionLoading}
                className="flex-1 flex items-center justify-center gap-2 px-6 py-3 rounded-lg text-white font-medium transition-colors"
                style={{
                  backgroundColor: proposal.brand_primary_color || "#3b82f6",
                }}
              >
                {actionLoading ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  <CheckCircle className="w-5 h-5" />
                )}
                Aceptar Propuesta
              </button>
              <button
                onClick={handleReject}
                disabled={actionLoading}
                className="flex-1 flex items-center justify-center gap-2 px-6 py-3 bg-white border-2 rounded-lg font-medium transition-colors"
                style={{
                  borderColor: proposal.brand_secondary_color || "#1e40af",
                  color: proposal.brand_secondary_color || "#1e40af",
                }}
              >
                {actionLoading ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  <XCircle className="w-5 h-5" />
                )}
                Rechazar
              </button>
            </div>
            <div className="mt-4">
              <textarea
                value={feedback}
                onChange={(e) => setFeedback(e.target.value)}
                placeholder="¿Tienes comentarios o quieres solicitar cambios? (opcional)"
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500"
                rows={3}
              />
            </div>
          </div>
        )}

        {proposal.status === "accepted" && (
          <div className="mt-8 p-4 bg-green-50 border border-green-200 rounded-xl text-center">
            <CheckCircle className="w-8 h-8 text-green-500 mx-auto mb-2" />
            <p className="text-green-800 font-medium">
              Esta propuesta ya fue aceptada.
            </p>
          </div>
        )}

        {proposal.status === "rejected" && (
          <div className="mt-8 p-4 bg-red-50 border border-red-200 rounded-xl text-center">
            <XCircle className="w-8 h-8 text-red-500 mx-auto mb-2" />
            <p className="text-red-800 font-medium">
              Esta propuesta fue rechazada.
            </p>
          </div>
        )}

        {/* Footer */}
        <div className="mt-8 text-center text-sm text-gray-400">
          <p>
            Propuesta generada por{" "}
            <span className="font-medium">Eko AI</span>
          </p>
          <p className="mt-1">
            {new Date(proposal.created_at).toLocaleDateString("es-MX", {
              year: "numeric",
              month: "long",
              day: "numeric",
            })}
          </p>
        </div>
      </div>
    </div>
  );
}
