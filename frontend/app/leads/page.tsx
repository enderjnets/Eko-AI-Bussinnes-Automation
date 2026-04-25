"use client";

import { useState, useEffect } from "react";
import { Search, Filter, Loader2, MapPin, Mail, Phone, Globe, Sparkles, Brain } from "lucide-react";
import Link from "next/link";
import Navbar from "@/components/Navbar";
import { leadsApi } from "@/lib/api";

interface Lead {
  id: number;
  business_name: string;
  category: string;
  city: string;
  state: string;
  email?: string;
  phone?: string;
  website?: string;
  address?: string;
  status: string;
  urgency_score: number;
  fit_score: number;
  total_score: number;
  created_at: string;
}

export default function LeadsPage() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [semanticMode, setSemanticMode] = useState(false);
  const [enrichingId, setEnrichingId] = useState<number | null>(null);
  const [enrichmentStatus, setEnrichmentStatus] = useState<any>(null);
  const [showEnrichmentToast, setShowEnrichmentToast] = useState(false);

  useEffect(() => {
    loadLeads();
  }, [status]);

  useEffect(() => {
    loadEnrichmentStatus();
    const interval = setInterval(loadEnrichmentStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  const loadEnrichmentStatus = async () => {
    try {
      const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : "";
      const res = await fetch("http://10.0.0.240:8001/api/v1/leads/enrichment-status", {
        headers: { Authorization: `Bearer ${token}` }
      });
      const newStatus = await res.json();
      if (enrichmentStatus && newStatus.scored > enrichmentStatus.scored) {
        setShowEnrichmentToast(true);
        setTimeout(() => setShowEnrichmentToast(false), 5000);
        loadLeads();
      }
      setEnrichmentStatus(newStatus);
    } catch (err) {
      // silently fail
    }
  };

  const loadLeads = async () => {
    setLoading(true);
    try {
      let res;
      if (semanticMode && search.trim()) {
        res = await leadsApi.search({ query: search.trim(), status: status || undefined });
      } else {
        res = await leadsApi.list({ status: status || undefined, search: search || undefined });
      }
      setLeads(res.data.items || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    loadLeads();
  };

  const handleEnrich = async (id: number) => {
    setEnrichingId(id);
    try {
      await leadsApi.enrich(id);
      loadLeads();
    } catch (err) {
      console.error(err);
    } finally {
      setEnrichingId(null);
    }
  };

  const getScoreColor = (score: number) => {
    if (score >= 70) return "text-eko-green";
    if (score >= 50) return "text-gold";
    if (score >= 30) return "text-orange-400";
    return "text-gray-500";
  };

  return (
    <div className="min-h-screen bg-eko-graphite">
      <Navbar />
      {/* Enrichment toast notification */}
      {showEnrichmentToast && (
        <div className="fixed top-20 right-4 z-50 animate-in slide-in-from-top-2">
          <div className="rounded-lg bg-eko-green/90 backdrop-blur border border-eko-green/50 px-4 py-3 shadow-lg">
            <p className="text-sm font-medium text-white flex items-center gap-2">
              <Sparkles className="w-4 h-4" />
              Nuevos leads enriquecidos con AI
            </p>
          </div>
        </div>
      )}
      <main className="pt-20 pb-12 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold font-display">Leads</h1>
            <p className="text-gray-400 text-sm">Gestiona y enriquece tus prospectos</p>
          </div>
        </div>

        <form onSubmit={handleSearch} className="flex gap-3 mb-6">
          <div className="relative flex-1">
            {semanticMode ? (
              <Brain className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-eko-green" />
            ) : (
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
            )}
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={semanticMode ? "Búsqueda semántica (ej: restaurantes con malas reseñas)..." : "Buscar por nombre..."}
              className={`w-full rounded-lg border bg-white/5 pl-10 pr-4 py-2.5 text-sm focus:outline-none ${
                semanticMode ? "border-eko-green/50 focus:border-eko-green focus:ring-1 focus:ring-eko-green" : "border-white/10 focus:border-eko-blue"
              }`}
            />
          </div>
          <button
            type="button"
            onClick={() => setSemanticMode((prev) => !prev)}
            className={`flex items-center gap-2 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
              semanticMode
                ? "bg-eko-green/20 text-eko-green border border-eko-green/30"
                : "bg-white/5 text-gray-400 border border-white/10 hover:bg-white/10"
            }`}
            title="Toggle semantic search"
          >
            <Brain className="w-4 h-4" />
            <span className="hidden sm:inline">{semanticMode ? "Semántica" : "Texto"}</span>
          </button>
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="rounded-lg border border-white/10 bg-white/5 px-4 py-2.5 text-sm focus:border-eko-blue focus:outline-none"
          >
            <option value="">Todos los estados</option>
            <option value="discovered">Descubiertos</option>
            <option value="enriched">Enriquecidos</option>
            <option value="scored">Scoring</option>
            <option value="contacted">Contactados</option>
            <option value="engaged">Engaged</option>
            <option value="closed_won">Ganados</option>
            <option value="closed_lost">Perdidos</option>
          </select>
          <button
            type="submit"
            className="rounded-lg bg-eko-blue px-4 py-2.5 text-sm font-medium hover:bg-eko-blue-dark transition-colors"
          >
            <Filter className="w-4 h-4" />
          </button>
        </form>

        {loading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-8 h-8 animate-spin text-eko-blue" />
          </div>
        ) : leads.length === 0 ? (
          <div className="text-center py-20 text-gray-500">
            <p>No se encontraron leads.</p>
          </div>
        ) : (
          <div className="rounded-xl border border-white/5 bg-white/[0.02] overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b border-white/5 text-left text-xs text-gray-500 uppercase">
                  <th className="px-4 py-3">Negocio</th>
                  <th className="px-4 py-3">Ubicación</th>
                  <th className="px-4 py-3">Contacto</th>
                  <th className="px-4 py-3">Score</th>
                  <th className="px-4 py-3">Estado</th>
                  <th className="px-4 py-3">Acciones</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {leads.map((lead) => (
                  <tr key={lead.id} className="hover:bg-white/[0.02] transition-colors">
                    <td className="px-4 py-3">
                      <div>
                        <Link href={`/leads/${lead.id}`} className="font-medium text-sm hover:text-eko-blue transition-colors">{lead.business_name}</Link>
                        {lead.category && (
                          <p className="text-xs text-gray-500">{lead.category}</p>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span className="flex items-center gap-1 text-sm text-gray-400">
                        <MapPin className="w-3 h-3" />
                        {lead.address || `${lead.city}, ${lead.state}`}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-col gap-1">
                        {lead.phone && (
                          <a href={`tel:${lead.phone}`} className="flex items-center gap-1 text-xs text-gray-400 hover:text-white">
                            <Phone className="w-3 h-3" />
                            {lead.phone}
                          </a>
                        )}
                        {lead.email && (
                          <a href={`mailto:${lead.email}`} className="flex items-center gap-1 text-xs text-gray-400 hover:text-white">
                            <Mail className="w-3 h-3" />
                            {lead.email}
                          </a>
                        )}
                        {lead.website && (
                          <a href={lead.website} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1 text-xs text-eko-blue hover:underline">
                            <Globe className="w-3 h-3" />
                            Web
                          </a>
                        )}
                        {!lead.phone && !lead.email && !lead.website && (
                          <span className="text-xs text-gray-600">Sin datos de contacto</span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      {lead.total_score > 0 ? (
                        <span className={`font-bold font-display ${getScoreColor(lead.total_score)}`}>
                          {Math.round(lead.total_score)}
                        </span>
                      ) : (
                        <span className="text-gray-600 text-sm">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-xs px-2 py-1 rounded-full bg-white/5 text-gray-400 capitalize">
                        {lead.status.replace("_", " ")}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {lead.status === "discovered" && (
                        <button
                          onClick={() => handleEnrich(lead.id)}
                          disabled={enrichingId === lead.id}
                          className="flex items-center gap-1 text-xs text-eko-blue hover:text-eko-blue-dark disabled:opacity-50"
                        >
                          {enrichingId === lead.id ? (
                            <Loader2 className="w-3 h-3 animate-spin" />
                          ) : (
                            <Sparkles className="w-3 h-3" />
                          )}
                          Enriquecer
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </div>
  );
}
