"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import {
  Search,
  Filter,
  Loader2,
  MapPin,
  Mail,
  Phone,
  Globe,
  Sparkles,
  Brain,
  Navigation,
  Target,
  X,
  ChevronDown,
  Send,
} from "lucide-react";
import Link from "next/link";
import Navbar from "@/components/Navbar";
import { leadsApi, phoneCallsApi } from "@/lib/api";

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
  latitude?: number;
  longitude?: number;
  distance_km?: number;
  created_at: string;
}

const DEFAULT_HQ_ADDRESS = "6000 S Fraser St, Aurora, CO 80016";
const HQ_STORAGE_KEY = "eko_hq_address";
const HQ_COORDS_KEY = "eko_hq_coords";

type SortMode = "score" | "distance" | "score_distance";

// Sanitize website URLs to prevent XSS via javascript: protocol
function sanitizeUrl(url?: string): string | undefined {
  if (!url) return undefined;
  const trimmed = url.trim();
  // Allow http:, https:, mailto:, tel:
  if (/^(https?:|mailto:|tel:)/i.test(trimmed)) {
    return trimmed;
  }
  // If it looks like a domain without protocol, prepend https://
  if (/^[a-z0-9][\w\-\.]*\.[a-z]{2,}/i.test(trimmed)) {
    return `https://${trimmed}`;
  }
  return undefined;
}

// Client-side Haversine (km)
function haversineKm(lat1: number, lng1: number, lat2?: number, lng2?: number): number | null {
  if (lat2 == null || lng2 == null) return null;
  const R = 6371;
  const dlat = ((lat2 - lat1) * Math.PI) / 180;
  const dlng = ((lng2 - lng1) * Math.PI) / 180;
  const a =
    Math.sin(dlat / 2) * Math.sin(dlat / 2) +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dlng / 2) *
      Math.sin(dlng / 2);
  const clampedA = Math.min(1.0, Math.max(0.0, a));
  const c = 2 * Math.atan2(Math.sqrt(clampedA), Math.sqrt(1 - clampedA));
  return R * c;
}

async function geocodeAddress(address: string): Promise<{ lat: number; lng: number } | null> {
  if (!address.trim()) return null;
  try {
    const url = `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(address)}&limit=1`;
    const res = await fetch(url, { headers: { "User-Agent": "EkoAI-LeadManager/1.0" } });
    const data = await res.json();
    if (data && data.length > 0) {
      return { lat: parseFloat(data[0].lat), lng: parseFloat(data[0].lon) };
    }
  } catch (err) {
    console.error("Geocoding failed:", err);
  }
  return null;
}

export default function LeadsPage() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [semanticMode, setSemanticMode] = useState(false);
  const [enrichingId, setEnrichingId] = useState<number | null>(null);
  const [enrichmentStatus, setEnrichmentStatus] = useState<any>(null);
  const enrichmentStatusRef = useRef(enrichmentStatus);
  useEffect(() => { enrichmentStatusRef.current = enrichmentStatus; }, [enrichmentStatus]);
  const [showEnrichmentToast, setShowEnrichmentToast] = useState(false);
  const [bulkEnriching, setBulkEnriching] = useState(false);
  const [totalLeads, setTotalLeads] = useState(0);
  const [page, setPage] = useState(1);
  const [sortBy, setSortBy] = useState<SortMode>("score_distance");
  const [error, setError] = useState<string | null>(null);

  // Advanced filters
  const [minScore, setMinScore] = useState<string>("");
  const [maxScore, setMaxScore] = useState<string>("");
  const [filterCity, setFilterCity] = useState<string>("");
  const [filterCategory, setFilterCategory] = useState<string>("");
  const [hasEmail, setHasEmail] = useState<boolean | null>(null);
  const [hasPhone, setHasPhone] = useState<boolean | null>(null);
  const [hasWebsite, setHasWebsite] = useState<boolean | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  // Bulk selection
  const [selectedLeads, setSelectedLeads] = useState<Set<number>>(new Set());
  const [bulkContacting, setBulkContacting] = useState(false);
  const [bulkContactResult, setBulkContactResult] = useState<string | null>(null);

  // Call modal
  const [callModalLead, setCallModalLead] = useState<Lead | null>(null);
  const [callResult, setCallResult] = useState("NO_ANSWER");
  const [callNotes, setCallNotes] = useState("");
  const [callInterest, setCallInterest] = useState("MEDIUM");
  const [callNextAction, setCallNextAction] = useState("CALL_AGAIN");
  const [callLogging, setCallLogging] = useState(false);

  // Headquarters
  const [hqAddress, setHqAddress] = useState(DEFAULT_HQ_ADDRESS);
  const [hqCoords, setHqCoords] = useState<{ lat: number; lng: number } | null>(null);
  const [editingHq, setEditingHq] = useState(false);
  const [hqInput, setHqInput] = useState(DEFAULT_HQ_ADDRESS);
  const [geocoding, setGeocoding] = useState(false);

  // Autocomplete
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [suggestLoading, setSuggestLoading] = useState(false);
  const autocompleteRef = useRef<HTMLDivElement>(null);
  const searchDebounceRef = useRef<NodeJS.Timeout | null>(null);
  const filterDebounceRef = useRef<NodeJS.Timeout | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Load HQ from localStorage
  useEffect(() => {
    const savedAddr = localStorage.getItem(HQ_STORAGE_KEY);
    const savedCoords = localStorage.getItem(HQ_COORDS_KEY);
    if (savedAddr) {
      setHqAddress(savedAddr);
      setHqInput(savedAddr);
    }
    if (savedCoords) {
      try {
        setHqCoords(JSON.parse(savedCoords));
      } catch {
        /* ignore */
      }
    } else {
      geocodeAddress(savedAddr || DEFAULT_HQ_ADDRESS).then((coords) => {
        if (coords) {
          setHqCoords(coords);
          localStorage.setItem(HQ_COORDS_KEY, JSON.stringify(coords));
        }
      });
    }
  }, []);

  // Fetch leads — debounce advanced filter changes to avoid firing on every keystroke
  useEffect(() => {
    if (filterDebounceRef.current) clearTimeout(filterDebounceRef.current);
    filterDebounceRef.current = setTimeout(() => {
      loadLeads();
    }, 300);
    return () => {
      if (filterDebounceRef.current) clearTimeout(filterDebounceRef.current);
    };
  }, [status, page, sortBy, hqCoords, search, semanticMode, minScore, maxScore, filterCity, filterCategory, hasEmail, hasPhone, hasWebsite]);

  // Close autocomplete on outside click
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (autocompleteRef.current && !autocompleteRef.current.contains(e.target as Node)) {
        setShowSuggestions(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Autocomplete debounce
  useEffect(() => {
    if (searchDebounceRef.current) clearTimeout(searchDebounceRef.current);
    if (!search.trim() || semanticMode) {
      setSuggestions([]);
      setShowSuggestions(false);
      return;
    }
    searchDebounceRef.current = setTimeout(async () => {
      setSuggestLoading(true);
      try {
        const res = await leadsApi.autocomplete(search.trim(), 8);
        setSuggestions(res.data || []);
        setShowSuggestions((res.data || []).length > 0);
      } catch {
        setSuggestions([]);
      } finally {
        setSuggestLoading(false);
      }
    }, 250);
    return () => {
      if (searchDebounceRef.current) clearTimeout(searchDebounceRef.current);
    };
  }, [search, semanticMode]);

  const loadEnrichmentStatus = useCallback(async () => {
    try {
      const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : "";
      const res = await fetch("/api/v1/leads/enrichment-status", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        console.warn("enrichment-status failed:", res.status);
        return;
      }
      const newStatus = await res.json();
      const prev = enrichmentStatusRef.current;
      if (prev && newStatus.scored > prev.scored) {
        setShowEnrichmentToast(true);
        setTimeout(() => setShowEnrichmentToast(false), 5000);
        loadLeads();
      }
      setEnrichmentStatus(newStatus);
    } catch (err) {
      console.warn("enrichment-status error:", err);
    }
  }, []);

  // Enrichment polling
  useEffect(() => {
    loadEnrichmentStatus();
    const interval = setInterval(loadEnrichmentStatus, 10000);
    return () => clearInterval(interval);
  }, [loadEnrichmentStatus]);

  const applyClientSort = useCallback(
    (items: Lead[]): Lead[] => {
      if (!items.length) return items;
      const arr = [...items];

      // Only apply client-side sort when backend did NOT do geo-sorting
      // (i.e. when hqCoords exists, backend handles all geo sorts)
      if (hqCoords) return arr;

      if (sortBy === "score" || sortBy === "score_distance") {
        arr.sort((a, b) => (b.total_score || 0) - (a.total_score || 0));
        return arr;
      }

      return arr;
    },
    [sortBy, hqCoords]
  );

  const loadLeads = useCallback(async () => {
    // Cancel any in-flight request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;

    setLoading(true);
    setError(null);
    try {
      let items: Lead[] = [];
      let total = 0;

      if (semanticMode && search.trim()) {
        const res = await leadsApi.search({ query: search.trim(), status: status || undefined });
        items = res.data.items || [];
        total = items.length;
      } else {
        const params: any = {
          status: status || undefined,
          search: search || undefined,
          page_size: 100,
          page: page,
          sort_by: sortBy,
          min_score: minScore ? parseFloat(minScore) : undefined,
          max_score: maxScore ? parseFloat(maxScore) : undefined,
          city: filterCity || undefined,
          category: filterCategory || undefined,
          has_email: hasEmail ?? undefined,
          has_phone: hasPhone ?? undefined,
          has_website: hasWebsite ?? undefined,
        };
        if (hqCoords && sortBy !== "score") {
          params.lat = hqCoords.lat;
          params.lng = hqCoords.lng;
        }
        const res = await leadsApi.list(params);
        items = res.data.items || [];
        total = res.data.total || 0;

        // Only apply client-side sort when backend didn't do geo-sort
        if (!hqCoords) {
          items = applyClientSort(items);
        }
      }

      if (!controller.signal.aborted) {
        setLeads(items);
        setTotalLeads(total);
      }
    } catch (err: any) {
      if (err.name === "CanceledError" || err.name === "AbortError") return;
      console.error(err);
      setError(err.response?.data?.detail || "Error cargando leads");
    } finally {
      if (!controller.signal.aborted) {
        setLoading(false);
      }
    }
  }, [search, status, page, sortBy, hqCoords, semanticMode, applyClientSort, minScore, maxScore, filterCity, filterCategory, hasEmail, hasPhone, hasWebsite]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setShowSuggestions(false);
    setPage(1);
    loadLeads();
  };

  const [enrichError, setEnrichError] = useState<string | null>(null);

  const handleEnrich = async (id: number) => {
    setEnrichingId(id);
    setEnrichError(null);
    try {
      await leadsApi.enrich(id);
      loadLeads();
    } catch (err: any) {
      console.error(err);
      setEnrichError(err.response?.data?.detail || "Error enriqueciendo lead");
      setTimeout(() => setEnrichError(null), 5000);
    } finally {
      setEnrichingId(null);
    }
  };

  const handleSaveHq = async () => {
    if (!hqInput.trim()) return;
    setGeocoding(true);
    const coords = await geocodeAddress(hqInput.trim());
    setGeocoding(false);
    if (coords) {
      setHqAddress(hqInput.trim());
      setHqCoords(coords);
      localStorage.setItem(HQ_STORAGE_KEY, hqInput.trim());
      localStorage.setItem(HQ_COORDS_KEY, JSON.stringify(coords));
      setEditingHq(false);
      setPage(1);
      loadLeads();
    } else {
      alert("No se pudo geocodificar la dirección. Intenta con un formato más específico.");
    }
  };

  // Bulk selection handlers
  const toggleSelectLead = (id: number) => {
    setSelectedLeads((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selectedLeads.size === leads.length) {
      setSelectedLeads(new Set());
    } else {
      setSelectedLeads(new Set(leads.map((l) => l.id)));
    }
  };

  const handleBulkContact = async () => {
    if (selectedLeads.size === 0) return;
    const ids = Array.from(selectedLeads);
    setBulkContacting(true);
    setBulkContactResult(null);
    try {
      const res = await leadsApi.bulkContact(ids, "initial_outreach");
      const data = res.data;
      setBulkContactResult(`Enviados: ${data.sent} / Fallidos: ${data.failed}`);
      setSelectedLeads(new Set());
      loadLeads();
      setTimeout(() => setBulkContactResult(null), 5000);
    } catch (err: any) {
      console.error(err);
      setBulkContactResult(err.response?.data?.detail || "Error enviando emails");
      setTimeout(() => setBulkContactResult(null), 5000);
    } finally {
      setBulkContacting(false);
    }
  };

  const handleLogCall = async () => {
    if (!callModalLead) return;
    setCallLogging(true);
    try {
      await phoneCallsApi.create({
        lead_id: callModalLead.id,
        result: callResult,
        notes: callNotes || undefined,
        interest_level: callInterest,
        next_action: callNextAction,
      });
      setCallModalLead(null);
      setCallResult("NO_ANSWER");
      setCallNotes("");
      setCallInterest("MEDIUM");
      setCallNextAction("CALL_AGAIN");
      loadLeads();
    } catch (err: any) {
      console.error(err);
      alert(err.response?.data?.detail || "Error guardando llamada");
    } finally {
      setCallLogging(false);
    }
  };

  const getScoreColor = (score: number) => {
    if (score >= 70) return "text-eko-green";
    if (score >= 50) return "text-gold";
    if (score >= 30) return "text-orange-400";
    return "text-gray-500";
  };

  const sortLabel: Record<SortMode, string> = {
    score: "Mejor Score",
    distance: "Más Cercanos",
    score_distance: "Score + Cercanía",
  };

  return (
    <div className="min-h-screen bg-eko-graphite">
      <Navbar />
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
      {enrichError && (
        <div className="fixed top-20 right-4 z-50 animate-in slide-in-from-top-2">
          <div className="rounded-lg bg-red-500/90 backdrop-blur border border-red-400/50 px-4 py-3 shadow-lg">
            <p className="text-sm font-medium text-white">{enrichError}</p>
          </div>
        </div>
      )}
      <main className="pt-20 pb-12 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-6 gap-4">
          <div>
            <h1 className="text-2xl font-bold font-display">Leads</h1>
            <p className="text-gray-400 text-sm">Gestiona y enriquece tus prospectos</p>
          </div>

          <div className="flex items-center gap-2 text-sm">
            <Target className="w-4 h-4 text-eko-blue" />
            {editingHq ? (
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={hqInput}
                  onChange={(e) => setHqInput(e.target.value)}
                  placeholder="Dirección HQ..."
                  className="w-64 rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-sm focus:border-eko-blue focus:outline-none"
                  onKeyDown={(e) => e.key === "Enter" && handleSaveHq()}
                />
                <button
                  onClick={handleSaveHq}
                  disabled={geocoding}
                  className="rounded-lg bg-eko-blue px-3 py-1.5 text-xs font-medium hover:bg-eko-blue-dark disabled:opacity-50"
                >
                  {geocoding ? <Loader2 className="w-3 h-3 animate-spin" /> : "Guardar"}
                </button>
                <button
                  onClick={() => { setEditingHq(false); setHqInput(hqAddress); }}
                  className="p-1.5 rounded-lg hover:bg-white/10 text-gray-400"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
            ) : (
              <button
                onClick={() => setEditingHq(true)}
                className="flex items-center gap-1.5 text-gray-400 hover:text-white transition-colors"
                title="Cambiar dirección de referencia"
              >
                <span className="truncate max-w-[240px]">{hqAddress}</span>
                <ChevronDown className="w-3 h-3" />
              </button>
            )}
          </div>
        </div>

        {/* Smart Filter Bar */}
        <form onSubmit={handleSearch} className="flex flex-wrap gap-3 mb-6">
          <div className="relative flex-1 min-w-[200px]" ref={autocompleteRef}>
            {semanticMode ? (
              <Brain className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-eko-green z-10" />
            ) : (
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500 z-10" />
            )}
            <input
              type="text"
              value={search}
              onChange={(e) => { setSearch(e.target.value); setShowSuggestions(true); }}
              onFocus={() => search.trim() && suggestions.length > 0 && setShowSuggestions(true)}
              placeholder={semanticMode ? "Búsqueda semántica (ej: restaurantes con malas reseñas)..." : "Buscar por nombre, ciudad, dirección..."}
              className={`w-full rounded-lg border bg-white/5 pl-10 pr-4 py-2.5 text-sm focus:outline-none relative z-0 ${
                semanticMode ? "border-eko-green/50 focus:border-eko-green focus:ring-1 focus:ring-eko-green" : "border-white/10 focus:border-eko-blue"
              }`}
            />
            {suggestLoading && (
              <Loader2 className="absolute right-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 animate-spin text-gray-500" />
            )}

            {/* Autocomplete dropdown */}
            {showSuggestions && !semanticMode && (
              <div className="absolute top-full left-0 right-0 mt-1 rounded-lg border border-white/10 bg-eko-graphite shadow-xl z-50 overflow-hidden">
                {suggestions.map((s, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => {
                      setSearch(s);
                      setShowSuggestions(false);
                      setPage(1);
                      loadLeads();
                    }}
                    className="w-full text-left px-4 py-2 text-sm text-gray-300 hover:bg-white/5 transition-colors"
                  >
                    <span className="font-medium text-white">{s.slice(0, search.length)}</span>
                    <span>{s.slice(search.length)}</span>
                  </button>
                ))}
              </div>
            )}
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
            onChange={(e) => { setStatus(e.target.value); setPage(1); }}
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

          <select
            value={sortBy}
            onChange={(e) => { setSortBy(e.target.value as SortMode); setPage(1); }}
            className="rounded-lg border border-white/10 bg-white/5 px-4 py-2.5 text-sm focus:border-eko-blue focus:outline-none"
          >
            <option value="score_distance">Score + Cercanía</option>
            <option value="score">Mejor Score</option>
            <option value="distance">Más Cercanos</option>
          </select>

          <button
            type="submit"
            className="rounded-lg bg-eko-blue px-4 py-2.5 text-sm font-medium hover:bg-eko-blue-dark transition-colors"
          >
            <Filter className="w-4 h-4" />
          </button>
        </form>

        {/* Advanced Filters Toggle */}
        <div className="flex items-center gap-2 mb-3">
          <button
            type="button"
            onClick={() => setShowAdvanced((prev) => !prev)}
            className="text-xs text-gray-400 hover:text-white flex items-center gap-1 transition-colors"
          >
            <Filter className="w-3 h-3" />
            {showAdvanced ? "Ocultar filtros avanzados" : "Filtros avanzados"}
          </button>
        </div>

        {/* Advanced Filters Panel */}
        {showAdvanced && (
          <div className="mb-4 rounded-xl border border-white/5 bg-white/[0.02] p-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Score mínimo</label>
              <input
                type="number"
                min={0}
                max={100}
                value={minScore}
                onChange={(e) => { setMinScore(e.target.value); setPage(1); }}
                placeholder="0"
                className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm focus:border-eko-blue focus:outline-none"
              />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Score máximo</label>
              <input
                type="number"
                min={0}
                max={100}
                value={maxScore}
                onChange={(e) => { setMaxScore(e.target.value); setPage(1); }}
                placeholder="100"
                className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm focus:border-eko-blue focus:outline-none"
              />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Ciudad</label>
              <input
                type="text"
                value={filterCity}
                onChange={(e) => { setFilterCity(e.target.value); setPage(1); }}
                placeholder="Ej: Denver"
                className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm focus:border-eko-blue focus:outline-none"
              />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Categoría</label>
              <input
                type="text"
                value={filterCategory}
                onChange={(e) => { setFilterCategory(e.target.value); setPage(1); }}
                placeholder="Ej: Dental"
                className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm focus:border-eko-blue focus:outline-none"
              />
            </div>
            <div className="sm:col-span-2 lg:col-span-4 flex flex-wrap gap-3">
              <label className="flex items-center gap-2 text-xs text-gray-400 cursor-pointer">
                <input
                  type="checkbox"
                  checked={hasEmail === true}
                  onChange={(e) => { setHasEmail(e.target.checked ? true : null); setPage(1); }}
                  className="rounded border-white/20 bg-white/5"
                />
                Tiene email
              </label>
              <label className="flex items-center gap-2 text-xs text-gray-400 cursor-pointer">
                <input
                  type="checkbox"
                  checked={hasPhone === true}
                  onChange={(e) => { setHasPhone(e.target.checked ? true : null); setPage(1); }}
                  className="rounded border-white/20 bg-white/5"
                />
                Tiene teléfono
              </label>
              <label className="flex items-center gap-2 text-xs text-gray-400 cursor-pointer">
                <input
                  type="checkbox"
                  checked={hasWebsite === true}
                  onChange={(e) => { setHasWebsite(e.target.checked ? true : null); setPage(1); }}
                  className="rounded border-white/20 bg-white/5"
                />
                Tiene web
              </label>
              <button
                type="button"
                onClick={() => {
                  setMinScore("");
                  setMaxScore("");
                  setFilterCity("");
                  setFilterCategory("");
                  setHasEmail(null);
                  setHasPhone(null);
                  setHasWebsite(null);
                  setPage(1);
                }}
                className="text-xs text-gray-500 hover:text-white transition-colors ml-auto"
              >
                Limpiar filtros
              </button>
            </div>
          </div>
        )}

        {/* Bulk actions */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            {enrichmentStatus && enrichmentStatus.discovered > 0 && (
              <button
                onClick={async () => {
                  setBulkEnriching(true);
                  try {
                    const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : "";
                    const res = await fetch("/api/v1/leads/enrich-all", {
                      method: "POST",
                      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
                    });
                    await res.json();
                    setShowEnrichmentToast(true);
                    setTimeout(() => setShowEnrichmentToast(false), 5000);
                  } catch (err) {
                    console.error(err);
                  } finally {
                    setBulkEnriching(false);
                  }
                }}
                disabled={bulkEnriching}
                className="flex items-center gap-2 rounded-lg bg-eko-green/20 border border-eko-green/30 px-4 py-2 text-sm font-medium text-eko-green hover:bg-eko-green/30 disabled:opacity-50 transition-colors"
              >
                {bulkEnriching ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Sparkles className="w-4 h-4" />
                )}
                Enriquecer Todos ({enrichmentStatus.discovered})
              </button>
            )}
            {selectedLeads.size > 0 && (
              <button
                onClick={handleBulkContact}
                disabled={bulkContacting}
                className="flex items-center gap-2 rounded-lg bg-eko-blue/20 border border-eko-blue/30 px-4 py-2 text-sm font-medium text-eko-blue hover:bg-eko-blue/30 disabled:opacity-50 transition-colors"
              >
                {bulkContacting ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Send className="w-4 h-4" />
                )}
                Enviar email a {selectedLeads.size} seleccionados
              </button>
            )}
            {bulkContactResult && (
              <span className="text-xs text-gray-400 animate-in fade-in">{bulkContactResult}</span>
            )}
          </div>
          {enrichmentStatus && (
            <div className="text-xs text-gray-500">
              {enrichmentStatus.scored ?? 0} scored · {enrichmentStatus.enriched ?? 0} enriched · {enrichmentStatus.discovered ?? 0} to discover
            </div>
          )}
        </div>

        {/* Progress bar */}
        {enrichmentStatus && (enrichmentStatus.discovered > 0 || enrichmentStatus.enriched > 0) && (
          <div className="mb-6 rounded-xl border border-white/5 bg-white/[0.02] p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="text-xs text-gray-400">
                <span className="text-eko-green font-medium">{(enrichmentStatus.scored ?? 0) + (enrichmentStatus.enriched ?? 0)}</span> processed &middot;{" "}
                <span className="text-gray-500">{enrichmentStatus.discovered ?? 0}</span> pending
                {" "}·{" "}
                <span className="text-gray-500">{enrichmentStatus.pipeline_total ?? enrichmentStatus.total}</span> pipeline
              </div>
              <div className="text-xs text-eko-green font-medium">
                {(() => {
                  const denom = enrichmentStatus.pipeline_total ?? enrichmentStatus.total ?? 1;
                  const pct = Math.round((((enrichmentStatus.scored ?? 0) + (enrichmentStatus.enriched ?? 0)) / denom) * 100);
                  return `${pct}%`;
                })()}
              </div>
            </div>
            <div className="w-full bg-white/10 rounded-full h-2.5 overflow-hidden">
              <div
                className="bg-gradient-to-r from-eko-green to-eko-blue h-2.5 rounded-full transition-all duration-700 ease-out"
                style={{
                  width: `${(() => {
                    const denom = enrichmentStatus.pipeline_total ?? enrichmentStatus.total ?? 1;
                    return Math.round((((enrichmentStatus.scored ?? 0) + (enrichmentStatus.enriched ?? 0)) / denom) * 100);
                  })()}%`,
                }}
              />
            </div>
            <div className="flex justify-between text-xs mt-1.5 text-gray-500">
              <span>Enrichment progress</span>
              <span>{enrichmentStatus.scored ?? 0} with score &middot; {enrichmentStatus.enriched ?? 0} enriched &middot; {enrichmentStatus.discovered ?? 0} to discover</span>
            </div>
          </div>
        )}

        {leads.length > 0 && (
          <div className="mt-3 text-xs text-gray-500 text-right">
            Mostrando {leads.length} de {totalLeads} leads
            {hqCoords && sortBy !== "score" && (
              <span className="ml-2 text-eko-blue">
                · Origen: {hqAddress}
              </span>
            )}
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-8 h-8 animate-spin text-eko-blue" />
          </div>
        ) : error ? (
          <div className="text-center py-20 text-red-400">
            <p>{error}</p>
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
                  <th className="px-4 py-3 w-8">
                    <input
                      type="checkbox"
                      checked={selectedLeads.size === leads.length && leads.length > 0}
                      onChange={toggleSelectAll}
                      className="rounded border-white/20 bg-white/5"
                    />
                  </th>
                  <th className="px-4 py-3">Negocio</th>
                  <th className="px-4 py-3">Ubicación</th>
                  <th className="px-4 py-3">Contacto</th>
                  <th className="px-4 py-3">Score</th>
                  {hqCoords && sortBy !== "score" && <th className="px-4 py-3">Distancia</th>}
                  <th className="px-4 py-3">Estado</th>
                  <th className="px-4 py-3">Acciones</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {leads.map((lead) => (
                  <tr key={lead.id} className="hover:bg-white/[0.02] transition-colors">
                    <td className="px-4 py-3 w-8">
                      <input
                        type="checkbox"
                        checked={selectedLeads.has(lead.id)}
                        onChange={() => toggleSelectLead(lead.id)}
                        className="rounded border-white/20 bg-white/5"
                      />
                    </td>
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
                        {(() => {
                          const safeUrl = sanitizeUrl(lead.website);
                          return safeUrl ? (
                            <a href={safeUrl} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1 text-xs text-eko-blue hover:underline">
                              <Globe className="w-3 h-3" />
                              Web
                            </a>
                          ) : null;
                        })()}
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
                    {hqCoords && sortBy !== "score" && (
                      <td className="px-4 py-3">
                        {typeof lead.distance_km === "number" && !Number.isNaN(lead.distance_km) ? (
                          <span className="flex items-center gap-1 text-xs text-gray-400">
                            <Navigation className="w-3 h-3 text-eko-blue" />
                            {lead.distance_km < 1
                              ? `${(lead.distance_km * 1000).toFixed(0)} m`
                              : `${lead.distance_km.toFixed(1)} km`}
                          </span>
                        ) : (
                          <span className="text-xs text-gray-600">—</span>
                        )}
                      </td>
                    )}
                    <td className="px-4 py-3">
                      <span className="text-xs px-2 py-1 rounded-full bg-white/5 text-gray-400 capitalize">
                        {lead.status.replace("_", " ")}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-col gap-1">
                        {(lead.status === "discovered" || lead.status === "enriched") && (
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
                            {lead.status === "enriched" ? "Re-enriquecer" : "Enriquecer"}
                          </button>
                        )}
                        {lead.phone && (
                          <button
                            onClick={() => setCallModalLead(lead)}
                            className="flex items-center gap-1 text-xs text-eko-green hover:text-eko-green-dark"
                          >
                            <Phone className="w-3 h-3" />
                            Llamar
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        {totalLeads > 0 && (
          <div className="flex items-center justify-between mt-4 px-2">
            <div className="text-xs text-gray-500">
              Página {page} de {Math.ceil(totalLeads / 100)}
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-medium text-gray-300 hover:bg-white/10 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                ← Anterior
              </button>
              <button
                onClick={() => setPage((p) => Math.min(Math.ceil(totalLeads / 100), p + 1))}
                disabled={page >= Math.ceil(totalLeads / 100)}
                className="rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-medium text-gray-300 hover:bg-white/10 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                Siguiente →
              </button>
            </div>
          </div>
        )}
      </main>

      {/* Call Log Modal */}
      {callModalLead && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="w-full max-w-md rounded-xl border border-white/10 bg-eko-graphite shadow-2xl">
            <div className="flex items-center justify-between px-5 py-4 border-b border-white/5">
              <h3 className="font-medium text-sm">Registrar llamada — {callModalLead.business_name}</h3>
              <button
                onClick={() => setCallModalLead(null)}
                className="p-1 rounded-lg hover:bg-white/10 text-gray-400"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="px-5 py-4 space-y-4">
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Resultado</label>
                <select
                  value={callResult}
                  onChange={(e) => setCallResult(e.target.value)}
                  className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm focus:border-eko-blue focus:outline-none"
                >
                  <option value="CONNECTED">Conectado</option>
                  <option value="NO_ANSWER">No contestó</option>
                  <option value="VOICEMAIL">Buzón de voz</option>
                  <option value="WRONG_NUMBER">Número equivocado</option>
                  <option value="BUSY">Ocupado</option>
                </select>
              </div>

              <div>
                <label className="text-xs text-gray-500 mb-1 block">Nivel de interés</label>
                <select
                  value={callInterest}
                  onChange={(e) => setCallInterest(e.target.value)}
                  className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm focus:border-eko-blue focus:outline-none"
                >
                  <option value="HIGH">Alto</option>
                  <option value="MEDIUM">Medio</option>
                  <option value="LOW">Bajo</option>
                  <option value="NONE">Sin interés</option>
                </select>
              </div>

              <div>
                <label className="text-xs text-gray-500 mb-1 block">Próximo paso</label>
                <select
                  value={callNextAction}
                  onChange={(e) => setCallNextAction(e.target.value)}
                  className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm focus:border-eko-blue focus:outline-none"
                >
                  <option value="CALL_AGAIN">Llamar de nuevo</option>
                  <option value="EMAIL">Enviar email</option>
                  <option value="CLOSE">Cerrar lead</option>
                </select>
              </div>

              <div>
                <label className="text-xs text-gray-500 mb-1 block">Notas</label>
                <textarea
                  value={callNotes}
                  onChange={(e) => setCallNotes(e.target.value)}
                  placeholder="Notas de la conversación..."
                  rows={3}
                  className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm focus:border-eko-blue focus:outline-none resize-none"
                />
              </div>

              {callModalLead.phone && (
                <a
                  href={`tel:${callModalLead.phone}`}
                  className="flex items-center justify-center gap-2 w-full rounded-lg bg-eko-green/20 border border-eko-green/30 py-2.5 text-sm font-medium text-eko-green hover:bg-eko-green/30 transition-colors"
                >
                  <Phone className="w-4 h-4" />
                  Llamar ahora — {callModalLead.phone}
                </a>
              )}
            </div>

            <div className="flex items-center gap-2 px-5 py-4 border-t border-white/5">
              <button
                onClick={handleLogCall}
                disabled={callLogging}
                className="flex-1 rounded-lg bg-eko-blue py-2.5 text-sm font-medium hover:bg-eko-blue-dark disabled:opacity-50 transition-colors"
              >
                {callLogging ? <Loader2 className="w-4 h-4 animate-spin mx-auto" /> : "Guardar"}
              </button>
              <button
                onClick={() => setCallModalLead(null)}
                className="rounded-lg border border-white/10 px-4 py-2.5 text-sm text-gray-400 hover:bg-white/5 transition-colors"
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
