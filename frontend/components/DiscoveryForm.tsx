"use client";

import { useState } from "react";
import { Search, Loader2, MapPin, Star, Linkedin, Landmark } from "lucide-react";
import { leadsApi } from "@/lib/api";

interface DiscoveryFormProps {
  onSuccess?: (data: any) => void;
}

export default function DiscoveryForm({ onSuccess }: DiscoveryFormProps) {
  const [query, setQuery] = useState("");
  const [city, setCity] = useState("Denver");
  const [state, setState] = useState("Colorado");
  const [maxResults, setMaxResults] = useState(50);

  const handleStateChange = (newState: string) => {
    setState(newState);
    if (newState === "Colorado") {
      setCity("Denver");
    } else {
      setCity("");
    }
  };

  const COLORADO_CITIES = [
    "Aurora", "Boulder", "Broomfield", "Castle Rock", "Centennial",
    "Colorado Springs", "Commerce City", "Denver", "Englewood", "Fort Collins",
    "Grand Junction", "Greeley", "Highlands Ranch", "Lakewood", "Littleton",
    "Longmont", "Loveland", "Parker", "Pueblo", "Thornton",
    "Westminster", "Arvada", "Brighton", "Canon City", "Durango",
    "Golden", "La Junta", "Lafayette", "Louisville", "Montrose"
  ];

  const US_STATES = [
    "Alabama", "Alaska", "Arizona", "Arkansas", "California",
    "Colorado", "Connecticut", "Delaware", "Florida", "Georgia",
    "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa",
    "Kansas", "Kentucky", "Louisiana", "Maine", "Maryland",
    "Massachusetts", "Michigan", "Minnesota", "Mississippi", "Missouri",
    "Montana", "Nebraska", "Nevada", "New Hampshire", "New Jersey",
    "New Mexico", "New York", "North Carolina", "North Dakota", "Ohio",
    "Oklahoma", "Oregon", "Pennsylvania", "Rhode Island", "South Carolina",
    "South Dakota", "Tennessee", "Texas", "Utah", "Vermont",
    "Virginia", "Washington", "West Virginia", "Wisconsin", "Wyoming",
    "District of Columbia"
  ];

  const MAX_RESULTS_OPTIONS = [10, 25, 50, 100, 200];
  const [sources, setSources] = useState<string[]>(["google_maps"]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [discoveryResult, setDiscoveryResult] = useState<{total: number; new: number; duplicates: number} | null>(null);

  const toggleSource = (source: string) => {
    setSources((prev) =>
      prev.includes(source) ? prev.filter((s) => s !== source) : [...prev, source]
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setError("");

    try {
      const res = await leadsApi.discover({
        query: query.trim(),
        city,
        state,
        max_results: maxResults,
        sources: sources.length > 0 ? sources : ["google_maps"],
      });
      const data = res.data;
      onSuccess?.(data);
      setQuery("");
      setDiscoveryResult({
        total: data.total_found || 0,
        new: data.new_leads || 0,
        duplicates: data.duplicates_skipped || 0,
      });
    } catch (err: any) {
      setError(err.response?.data?.detail || "Error en la búsqueda");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="rounded-xl border border-white/5 bg-white/[0.02] p-6">
      <h2 className="text-lg font-semibold font-display mb-4">Discovery</h2>
      
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm text-gray-400 mb-1">¿Qué tipo de negocio buscas?</label>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ej: restaurants, salons, plumbers..."
            className="w-full rounded-lg border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white placeholder-gray-500 focus:border-eko-blue focus:outline-none focus:ring-1 focus:ring-eko-blue"
          />
        </div>

        <div className="grid grid-cols-3 gap-3">
          <div>
            <label className="block text-sm text-gray-400 mb-1">Ciudad</label>
            {state === "Colorado" ? (
              <select
                value={city}
                onChange={(e) => setCity(e.target.value)}
                className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm focus:border-eko-blue focus:outline-none appearance-none"
              >
                {COLORADO_CITIES.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            ) : (
              <input
                type="text"
                value={city}
                onChange={(e) => setCity(e.target.value)}
                placeholder="Ej: Los Angeles, Miami..."
                className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm focus:border-eko-blue focus:outline-none"
              />
            )}
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Estado</label>
            <select
              value={state}
              onChange={(e) => handleStateChange(e.target.value)}
              className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm focus:border-eko-blue focus:outline-none appearance-none"
            >
              {US_STATES.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Max resultados</label>
            <select
              value={maxResults}
              onChange={(e) => setMaxResults(Number(e.target.value))}
              className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm focus:border-eko-blue focus:outline-none appearance-none"
            >
              {MAX_RESULTS_OPTIONS.map((n) => (
                <option key={n} value={n}>{n}</option>
              ))}
            </select>
          </div>
        </div>

        <div>
          <label className="block text-sm text-gray-400 mb-2">Fuentes</label>
          <div className="flex gap-2">
            <SourceToggle
              label="Google Maps"
              icon={<MapPin className="w-3 h-3" />}
              active={sources.includes("google_maps")}
              onClick={() => toggleSource("google_maps")}
            />
            <SourceToggle
              label="Yelp"
              icon={<Star className="w-3 h-3" />}
              active={sources.includes("yelp")}
              onClick={() => toggleSource("yelp")}
            />
            <SourceToggle
              label="LinkedIn"
              icon={<Linkedin className="w-3 h-3" />}
              active={sources.includes("linkedin")}
              onClick={() => toggleSource("linkedin")}
            />
            <SourceToggle
              label="Colorado SOS"
              icon={<Landmark className="w-3 h-3" />}
              active={sources.includes("colorado_sos")}
              onClick={() => toggleSource("colorado_sos")}
            />
          </div>
        </div>

        {discoveryResult && (
          <div className="rounded-lg bg-eko-green/10 border border-eko-green/20 p-3 text-sm">
            <p className="text-eko-green font-medium">
              {discoveryResult.new > 0
                ? `${discoveryResult.new} nuevos leads agregados a la base de datos`
                : "No hay leads nuevos en esta búsqueda"}
            </p>
            {discoveryResult.duplicates > 0 && (
              <p className="text-gray-400 text-xs mt-1">
                {discoveryResult.duplicates} ya existían en la base de datos
              </p>
            )}
          </div>
        )}

        {error && (
          <p className="text-sm text-red-400">{error}</p>
        )}

        <button
          type="submit"
          disabled={loading || !query.trim()}
          className="w-full flex items-center justify-center gap-2 rounded-lg bg-eko-blue px-4 py-2.5 text-sm font-medium text-white hover:bg-eko-blue-dark disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              Buscando...
            </>
          ) : (
            <>
              <Search className="w-4 h-4" />
              Buscar Leads
            </>
          )}
        </button>
      </form>
    </div>
  );
}

function SourceToggle({
  label,
  icon,
  active,
  onClick,
}: {
  label: string;
  icon: React.ReactNode;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-medium transition-colors border ${
        active
          ? "bg-eko-blue/20 border-eko-blue/40 text-eko-blue"
          : "bg-white/5 border-white/10 text-gray-400 hover:bg-white/10"
      }`}
    >
      {icon}
      {label}
    </button>
  );
}
