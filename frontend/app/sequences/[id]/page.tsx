"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Plus, Trash2, Loader2, Mail, Clock, CheckCircle, Play, Pause } from "lucide-react";
import Navbar from "@/components/Navbar";
import { sequencesApi } from "@/lib/api";

interface SequenceStep {
  id: number;
  position: number;
  step_type: string;
  name: string;
  template_key: string | null;
  subject_template: string | null;
  body_template: string | null;
  ai_generate: boolean;
  delay_hours: number | null;
}

interface SequenceEnrollment {
  id: number;
  lead_id: number;
  status: string;
  current_step_position: number;
  next_step_at: string | null;
}

interface Sequence {
  id: number;
  name: string;
  description: string | null;
  status: string;
  leads_entered: number;
  leads_completed: number;
  steps: SequenceStep[];
  enrollments: SequenceEnrollment[];
}

export default function SequenceDetailPage() {
  const params = useParams();
  const id = parseInt(params.id as string, 10);

  const [sequence, setSequence] = useState<Sequence | null>(null);
  const [loading, setLoading] = useState(true);
  const [showAddStep, setShowAddStep] = useState(false);
  const [addingStep, setAddingStep] = useState(false);

  // New step form
  const [stepName, setStepName] = useState("");
  const [stepType, setStepType] = useState("email");
  const [templateKey, setTemplateKey] = useState("initial_outreach");
  const [delayHours, setDelayHours] = useState("24");
  const [useAi, setUseAi] = useState(true);

  const loadSequence = useCallback(async () => {
    if (!id || isNaN(id)) return;
    setLoading(true);
    try {
      const res = await sequencesApi.get(id);
      setSequence(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadSequence();
  }, [loadSequence]);

  const handleAddStep = async () => {
    if (!stepName.trim()) return;
    setAddingStep(true);
    try {
      const data: any = {
        name: stepName.trim(),
        step_type: stepType,
        position: (sequence?.steps?.length || 0) + 1,
      };
      if (stepType === "email") {
        data.template_key = templateKey;
        data.ai_generate = useAi;
      }
      if (stepType === "wait") {
        data.delay_hours = parseInt(delayHours, 10) || 24;
      }
      await sequencesApi.addStep(id, data);
      setStepName("");
      setShowAddStep(false);
      loadSequence();
    } catch (err) {
      console.error(err);
    } finally {
      setAddingStep(false);
    }
  };

  const handleDeleteStep = async (stepId: number) => {
    if (!confirm("¿Eliminar este paso?")) return;
    try {
      await sequencesApi.deleteStep(id, stepId);
      loadSequence();
    } catch (err) {
      console.error(err);
    }
  };

  const handleToggleStatus = async () => {
    if (!sequence) return;
    const newStatus = sequence.status === "active" ? "paused" : "active";
    try {
      await sequencesApi.update(id, { status: newStatus });
      loadSequence();
    } catch (err) {
      console.error(err);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-eko-graphite">
        <Navbar />
        <main className="pt-20 pb-12 px-4 flex items-center justify-center">
          <Loader2 className="w-6 h-6 animate-spin text-eko-blue" />
        </main>
      </div>
    );
  }

  if (!sequence) {
    return (
      <div className="min-h-screen bg-eko-graphite">
        <Navbar />
        <main className="pt-20 pb-12 px-4 text-center text-gray-500">
          <p>Secuencia no encontrada.</p>
          <Link href="/sequences" className="text-eko-blue hover:underline text-sm mt-2 inline-block">
            ← Volver a secuencias
          </Link>
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-eko-graphite">
      <Navbar />
      <main className="pt-20 pb-12 px-4 sm:px-6 lg:px-8 max-w-5xl mx-auto">
        <div className="mb-6">
          <Link href="/sequences" className="text-sm text-gray-400 hover:text-white flex items-center gap-1 mb-3">
            <ArrowLeft className="w-3 h-3" />
            Volver a secuencias
          </Link>
          <div className="flex items-start justify-between">
            <div>
              <h1 className="text-2xl font-bold font-display">{sequence.name}</h1>
              {sequence.description && (
                <p className="text-gray-400 text-sm mt-1">{sequence.description}</p>
              )}
            </div>
            <button
              onClick={handleToggleStatus}
              className={`flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
                sequence.status === "active"
                  ? "bg-gold/20 border border-gold/30 text-gold hover:bg-gold/30"
                  : "bg-eko-green/20 border border-eko-green/30 text-eko-green hover:bg-eko-green/30"
              }`}
            >
              {sequence.status === "active" ? (
                <>
                  <Pause className="w-4 h-4" />
                  Pausar
                </>
              ) : (
                <>
                  <Play className="w-4 h-4" />
                  Activar
                </>
              )}
            </button>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-3 gap-4 mb-8">
          <div className="rounded-xl border border-white/5 bg-white/[0.02] p-4 text-center">
            <div className="text-2xl font-bold font-display text-eko-blue">{sequence.leads_entered}</div>
            <div className="text-xs text-gray-500 mt-1">Inscritos</div>
          </div>
          <div className="rounded-xl border border-white/5 bg-white/[0.02] p-4 text-center">
            <div className="text-2xl font-bold font-display text-eko-green">{sequence.leads_completed}</div>
            <div className="text-xs text-gray-500 mt-1">Completados</div>
          </div>
          <div className="rounded-xl border border-white/5 bg-white/[0.02] p-4 text-center">
            <div className="text-2xl font-bold font-display text-gold">
              {sequence.enrollments?.filter((e) => e.status === "active").length || 0}
            </div>
            <div className="text-xs text-gray-500 mt-1">Activos</div>
          </div>
        </div>

        {/* Steps */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-medium">Pasos de la secuencia</h2>
            <button
              onClick={() => setShowAddStep(true)}
              className="flex items-center gap-1 rounded-lg bg-eko-blue px-3 py-1.5 text-xs font-medium hover:bg-eko-blue-dark transition-colors"
            >
              <Plus className="w-3 h-3" />
              Agregar paso
            </button>
          </div>

          {showAddStep && (
            <div className="mb-4 rounded-xl border border-white/5 bg-white/[0.02] p-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-3">
                <input
                  type="text"
                  value={stepName}
                  onChange={(e) => setStepName(e.target.value)}
                  placeholder="Nombre del paso..."
                  className="rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm focus:border-eko-blue focus:outline-none"
                />
                <select
                  value={stepType}
                  onChange={(e) => setStepType(e.target.value)}
                  className="rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm focus:border-eko-blue focus:outline-none"
                >
                  <option value="email">Email</option>
                  <option value="wait">Espera</option>
                </select>
              </div>

              {stepType === "email" && (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-3">
                  <select
                    value={templateKey}
                    onChange={(e) => setTemplateKey(e.target.value)}
                    className="rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm focus:border-eko-blue focus:outline-none"
                  >
                    <option value="initial_outreach">Initial Outreach</option>
                    <option value="follow_up_1">Follow-up 1</option>
                    <option value="follow_up_2">Follow-up 2</option>
                    <option value="breakup">Breakup</option>
                    <option value="booking_confirmation">Booking Confirmation</option>
                  </select>
                  <label className="flex items-center gap-2 text-sm text-gray-400">
                    <input
                      type="checkbox"
                      checked={useAi}
                      onChange={(e) => setUseAi(e.target.checked)}
                      className="rounded border-white/20 bg-white/5"
                    />
                    Generar con AI
                  </label>
                </div>
              )}

              {stepType === "wait" && (
                <div className="mb-3">
                  <input
                    type="number"
                    value={delayHours}
                    onChange={(e) => setDelayHours(e.target.value)}
                    placeholder="Horas de espera..."
                    className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm focus:border-eko-blue focus:outline-none"
                  />
                </div>
              )}

              <div className="flex gap-2">
                <button
                  onClick={handleAddStep}
                  disabled={addingStep || !stepName.trim()}
                  className="rounded-lg bg-eko-blue px-4 py-2 text-sm font-medium hover:bg-eko-blue-dark disabled:opacity-50 transition-colors"
                >
                  {addingStep ? <Loader2 className="w-4 h-4 animate-spin" /> : "Agregar"}
                </button>
                <button
                  onClick={() => setShowAddStep(false)}
                  className="rounded-lg border border-white/10 px-4 py-2 text-sm text-gray-400 hover:bg-white/5 transition-colors"
                >
                  Cancelar
                </button>
              </div>
            </div>
          )}

          {sequence.steps?.length === 0 ? (
            <p className="text-sm text-gray-500">No hay pasos definidos.</p>
          ) : (
            <div className="space-y-3">
              {sequence.steps?.map((step, idx) => (
                <div
                  key={step.id}
                  className="flex items-center gap-4 rounded-xl border border-white/5 bg-white/[0.02] p-4"
                >
                  <div className="flex items-center justify-center w-8 h-8 rounded-full bg-white/5 text-xs font-medium text-gray-400">
                    {idx + 1}
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-sm">{step.name}</span>
                      <span className="text-xs px-2 py-0.5 rounded-full bg-white/5 text-gray-500 capitalize">
                        {step.step_type}
                      </span>
                    </div>
                    {step.step_type === "email" && (
                      <div className="text-xs text-gray-500 mt-1 flex items-center gap-2">
                        <Mail className="w-3 h-3" />
                        {step.template_key || "Sin template"}
                        {step.ai_generate && <span className="text-eko-blue">· AI</span>}
                      </div>
                    )}
                    {step.step_type === "wait" && step.delay_hours && (
                      <div className="text-xs text-gray-500 mt-1 flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        Espera {step.delay_hours}h
                      </div>
                    )}
                  </div>
                  <button
                    onClick={() => handleDeleteStep(step.id)}
                    className="p-2 rounded-lg hover:bg-red-500/10 text-gray-500 hover:text-red-400 transition-colors"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Enrollments */}
        <div>
          <h2 className="text-lg font-medium mb-4">Inscripciones activas</h2>
          {sequence.enrollments?.length === 0 ? (
            <p className="text-sm text-gray-500">No hay leads inscritos.</p>
          ) : (
            <div className="rounded-xl border border-white/5 bg-white/[0.02] overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-white/5 text-left text-xs text-gray-500 uppercase">
                    <th className="px-4 py-3">Lead ID</th>
                    <th className="px-4 py-3">Estado</th>
                    <th className="px-4 py-3">Paso actual</th>
                    <th className="px-4 py-3">Próximo paso</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {sequence.enrollments?.map((enr) => (
                    <tr key={enr.id} className="hover:bg-white/[0.02]">
                      <td className="px-4 py-3">{enr.lead_id}</td>
                      <td className="px-4 py-3">
                        <span className={`text-xs px-2 py-0.5 rounded-full capitalize ${
                          enr.status === "active" ? "text-eko-green bg-eko-green/10" :
                          enr.status === "completed" ? "text-eko-blue bg-eko-blue/10" :
                          "text-gray-400 bg-gray-500/10"
                        }`}>
                          {enr.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-gray-400">{enr.current_step_position}</td>
                      <td className="px-4 py-3 text-gray-400">
                        {enr.next_step_at ? new Date(enr.next_step_at).toLocaleString() : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
