"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Inbox,
  MailOpen,
  Mail,
  Loader2,
  Zap,
  CheckCircle,
  AlertCircle,
  Clock,
  ChevronDown,
  ChevronUp,
  Send,
  Smile,
  Meh,
  Frown,
  MessageSquare,
  Wand2,
  X,
  Edit3,
  ArrowLeft,
} from "lucide-react";
import Navbar from "@/components/Navbar";
import { emailsApi } from "@/lib/api";

interface InboxItem {
  id: number;
  lead_id: number;
  lead_name: string;
  lead_email: string;
  lead_status: string;
  subject: string;
  content: string;
  sentiment: string;
  intent: string;
  summary: string;
  next_action: string;
  priority: string;
  key_points: string[];
  read: boolean;
  auto_status_changed: boolean;
  previous_status: string;
  created_at: string;
}

interface AIReply {
  subject: string;
  body: string;
  tone: string;
  confidence: number;
  suggested_next_action: string;
}

interface ConversationItem {
  id: number;
  direction: string;
  subject: string;
  content: string;
  created_at: string;
}

export default function InboxPage() {
  const [items, setItems] = useState<InboxItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<"all" | "unread" | "high_priority">("all");
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [markingRead, setMarkingRead] = useState<number | null>(null);
  const [simulating, setSimulating] = useState(false);

  // AI Reply state
  const [showReplyModal, setShowReplyModal] = useState(false);
  const [replyTarget, setReplyTarget] = useState<InboxItem | null>(null);
  const [generatingReply, setGeneratingReply] = useState(false);
  const [aiReply, setAiReply] = useState<AIReply | null>(null);
  const [editedSubject, setEditedSubject] = useState("");
  const [editedBody, setEditedBody] = useState("");
  const [sendingReply, setSendingReply] = useState(false);
  const [replyTone, setReplyTone] = useState("professional");
  const [replyLength, setReplyLength] = useState("medium");
  const [replyError, setReplyError] = useState("");
  const [conversation, setConversation] = useState<ConversationItem[]>([]);
  const [loadingConversation, setLoadingConversation] = useState(false);

  const loadInbox = useCallback(async () => {
    setLoading(true);
    try {
      const params: any = {};
      if (filter === "unread") params.status = "unread";
      const res = await emailsApi.inbox(params);
      let data = res.data?.items || [];
      if (filter === "high_priority") {
        data = data.filter((i: InboxItem) => i.priority === "high");
      }
      setItems(data);
    } catch (err) {
      console.error("Failed to load inbox:", err);
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    loadInbox();
  }, [loadInbox]);

  const handleMarkRead = async (id: number) => {
    setMarkingRead(id);
    try {
      await emailsApi.markRead(id);
      setItems((prev) =>
        prev.map((item) => (item.id === id ? { ...item, read: true } : item))
      );
    } catch (err) {
      console.error(err);
    } finally {
      setMarkingRead(null);
    }
  };

  const handleSimulateReply = async () => {
    const leadId = prompt("Lead ID para simular reply:");
    if (!leadId) return;
    const subject = prompt("Asunto del reply:", "Re: Propuesta de colaboración");
    if (!subject) return;
    const body = prompt(
      "Contenido del reply:",
      "Me interesa saber más. ¿Podemos agendar una llamada esta semana?"
    );
    if (!body) return;

    setSimulating(true);
    try {
      await emailsApi.simulateReply(parseInt(leadId), subject, body);
      loadInbox();
    } catch (err) {
      console.error(err);
      alert("Error simulando reply");
    } finally {
      setSimulating(false);
    }
  };

  const openReplyModal = async (item: InboxItem) => {
    setReplyTarget(item);
    setShowReplyModal(true);
    setAiReply(null);
    setEditedSubject("");
    setEditedBody("");
    setReplyError("");
    setReplyTone("professional");
    setReplyLength("medium");

    // Load conversation
    setLoadingConversation(true);
    try {
      const res = await emailsApi.conversation(item.id);
      setConversation(res.data?.items || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingConversation(false);
    }
  };

  const handleGenerateReply = async () => {
    if (!replyTarget) return;
    setGeneratingReply(true);
    setReplyError("");
    try {
      const res = await emailsApi.aiReply(replyTarget.id, {
        tone: replyTone,
        max_length: replyLength,
      });
      const reply = res.data?.reply;
      setAiReply(reply);
      setEditedSubject(reply?.subject || "");
      setEditedBody(reply?.body || "");
    } catch (err: any) {
      setReplyError(err.response?.data?.detail || "Error generando respuesta");
    } finally {
      setGeneratingReply(false);
    }
  };

  const handleSendReply = async () => {
    if (!replyTarget) return;
    setSendingReply(true);
    setReplyError("");
    try {
      await emailsApi.sendReply(replyTarget.id, {
        subject: editedSubject,
        body: editedBody,
        send_email: true,
      });
      setShowReplyModal(false);
      setReplyTarget(null);
      setAiReply(null);
      loadInbox();
    } catch (err: any) {
      setReplyError(err.response?.data?.detail || "Error enviando respuesta");
    } finally {
      setSendingReply(false);
    }
  };

  const sentimentIcon = (s: string) => {
    switch (s) {
      case "positive":
        return <Smile className="w-4 h-4 text-eko-green" />;
      case "negative":
        return <Frown className="w-4 h-4 text-red-400" />;
      default:
        return <Meh className="w-4 h-4 text-gold" />;
    }
  };

  const priorityBadge = (p: string) => {
    switch (p) {
      case "high":
        return "bg-red-500/10 text-red-400 border-red-500/20";
      case "medium":
        return "bg-gold/10 text-gold border-gold/20";
      default:
        return "bg-gray-500/10 text-gray-400 border-gray-500/20";
    }
  };

  const intentLabel = (i: string) => {
    const map: Record<string, string> = {
      interested: "Interesado",
      needs_info: "Necesita info",
      not_interested: "No interesado",
      out_of_office: "Fuera de oficina",
      forwarded: "Reenviado",
      unclear: "No claro",
    };
    return map[i] || i;
  };

  const unreadCount = items.filter((i) => !i.read).length;

  return (
    <div className="min-h-screen bg-eko-graphite">
      <Navbar />
      <main className="pt-20 pb-12 px-4 sm:px-6 lg:px-8 max-w-5xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-eko-blue/10 text-eko-blue">
              <Inbox className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-2xl font-bold font-display">Inbox</h1>
              <p className="text-gray-400 text-sm">
                {unreadCount > 0
                  ? `${unreadCount} mensaje${unreadCount > 1 ? "s" : ""} sin leer`
                  : "No hay mensajes nuevos"}
              </p>
            </div>
          </div>
          <button
            onClick={handleSimulateReply}
            disabled={simulating}
            className="flex items-center gap-2 rounded-lg border border-white/10 px-4 py-2 text-sm text-gray-300 hover:bg-white/5 transition-colors disabled:opacity-50"
          >
            {simulating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
            Simular reply
          </button>
        </div>

        {/* Filters */}
        <div className="flex items-center gap-1 bg-white/5 rounded-lg p-1 mb-6 w-fit">
          {(["all", "unread", "high_priority"] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-3 py-1.5 rounded-md text-sm capitalize transition-colors ${
                filter === f
                  ? "bg-white/10 text-white"
                  : "text-gray-400 hover:text-white"
              }`}
            >
              {f === "high_priority" ? "Alta prioridad" : f === "unread" ? "Sin leer" : "Todos"}
            </button>
          ))}
        </div>

        {/* List */}
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-8 h-8 animate-spin text-eko-blue" />
          </div>
        ) : items.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-gray-500">
            <MailOpen className="w-12 h-12 mb-4 opacity-50" />
            <p className="text-lg font-medium">Inbox vacío</p>
            <p className="text-sm mt-1">
              {filter === "unread"
                ? "No hay mensajes sin leer"
                : filter === "high_priority"
                ? "No hay mensajes de alta prioridad"
                : "Los replies de leads aparecerán aquí"}
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {items.map((item) => {
              const isExpanded = expandedId === item.id;
              return (
                <div
                  key={item.id}
                  className={`rounded-xl border transition-colors ${
                    item.read
                      ? "border-white/5 bg-white/[0.02]"
                      : "border-eko-blue/20 bg-eko-blue/[0.02]"
                  }`}
                >
                  {/* Header row */}
                  <div
                    className="p-4 cursor-pointer"
                    onClick={() => setExpandedId(isExpanded ? null : item.id)}
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1 flex-wrap">
                          {!item.read && (
                            <span className="w-2 h-2 rounded-full bg-eko-blue" />
                          )}
                          <span className="font-medium text-sm truncate">
                            {item.lead_name}
                          </span>
                          <span className="text-xs text-gray-500">
                            {item.lead_email}
                          </span>
                          {item.auto_status_changed && (
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-eko-green/10 text-eko-green border border-eko-green/20">
                              Status auto-actualizado
                            </span>
                          )}
                        </div>
                        <p className="text-sm text-gray-300 truncate">
                          {item.subject || "(sin asunto)"}
                        </p>
                        <div className="flex items-center gap-3 mt-2 flex-wrap">
                          <span
                            className={`flex items-center gap-1 text-xs px-2 py-0.5 rounded-full border ${priorityBadge(
                              item.priority
                            )}`}
                          >
                            {item.priority}
                          </span>
                          <span className="flex items-center gap-1 text-xs text-gray-400">
                            {sentimentIcon(item.sentiment)}
                            {item.sentiment}
                          </span>
                          <span className="text-xs text-gray-500 capitalize">
                            {intentLabel(item.intent)}
                          </span>
                          <span className="text-xs text-gray-500 flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {new Date(item.created_at).toLocaleString("es-ES", {
                              day: "numeric",
                              month: "short",
                              hour: "2-digit",
                              minute: "2-digit",
                            })}
                          </span>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        {!item.read && (
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleMarkRead(item.id);
                            }}
                            disabled={markingRead === item.id}
                            className="p-1.5 rounded-lg text-gray-400 hover:text-eko-blue hover:bg-eko-blue/10 transition-colors"
                            title="Marcar como leído"
                          >
                            {markingRead === item.id ? (
                              <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                              <MailOpen className="w-4 h-4" />
                            )}
                          </button>
                        )}
                        {isExpanded ? (
                          <ChevronUp className="w-4 h-4 text-gray-500" />
                        ) : (
                          <ChevronDown className="w-4 h-4 text-gray-500" />
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Expanded content */}
                  {isExpanded && (
                    <div className="px-4 pb-4 border-t border-white/5 pt-3">
                      {/* AI Summary */}
                      {item.summary && (
                        <div className="mb-3 rounded-lg bg-white/5 p-3">
                          <div className="flex items-center gap-2 mb-1">
                            <Zap className="w-3.5 h-3.5 text-eko-blue" />
                            <span className="text-xs font-medium text-eko-blue">
                              Resumen AI
                            </span>
                          </div>
                          <p className="text-sm text-gray-300">{item.summary}</p>
                        </div>
                      )}

                      {/* Original content */}
                      <div className="mb-3">
                        <p className="text-sm text-gray-300 whitespace-pre-wrap">
                          {item.content}
                        </p>
                      </div>

                      {/* Key points */}
                      {item.key_points && item.key_points.length > 0 && (
                        <div className="mb-3">
                          <p className="text-xs text-gray-500 mb-1">Puntos clave:</p>
                          <ul className="space-y-1">
                            {item.key_points.map((point, idx) => (
                              <li
                                key={idx}
                                className="text-sm text-gray-300 flex items-start gap-2"
                              >
                                <AlertCircle className="w-3.5 h-3.5 text-gold mt-0.5 shrink-0" />
                                {point}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {/* Next action */}
                      {item.next_action && (
                        <div className="flex items-center gap-2 rounded-lg bg-eko-green/5 border border-eko-green/10 p-3 mb-3">
                          <CheckCircle className="w-4 h-4 text-eko-green shrink-0" />
                          <div>
                            <p className="text-xs text-gray-500">Acción recomendada</p>
                            <p className="text-sm text-eko-green">{item.next_action}</p>
                          </div>
                        </div>
                      )}

                      {/* Action buttons */}
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => openReplyModal(item)}
                          className="flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors text-sm"
                        >
                          <Wand2 className="w-4 h-4" />
                          Responder con IA
                        </button>
                      </div>

                      {/* Status change info */}
                      {item.auto_status_changed && (
                        <div className="mt-3 text-xs text-gray-500">
                          Status cambiado automáticamente: {item.previous_status} → {item.lead_status}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </main>

      {/* AI Reply Modal */}
      {showReplyModal && replyTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/60" onClick={() => setShowReplyModal(false)} />
          <div className="relative bg-eko-graphite border border-white/10 rounded-xl w-full max-w-3xl max-h-[90vh] overflow-hidden flex flex-col">
            {/* Modal header */}
            <div className="flex items-center justify-between p-4 border-b border-white/10">
              <div className="flex items-center gap-3">
                <MessageSquare className="w-5 h-5 text-purple-400" />
                <div>
                  <h3 className="font-semibold text-white">Responder a {replyTarget.lead_name}</h3>
                  <p className="text-xs text-gray-400">{replyTarget.subject}</p>
                </div>
              </div>
              <button
                onClick={() => setShowReplyModal(false)}
                className="p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-white/10 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal body */}
            <div className="flex-1 overflow-auto p-4 space-y-4">
              {/* Error */}
              {replyError && (
                <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400 text-sm">
                  {replyError}
                </div>
              )}

              {/* Conversation preview */}
              {loadingConversation ? (
                <div className="flex items-center justify-center py-4">
                  <Loader2 className="w-5 h-5 animate-spin text-gray-400" />
                </div>
              ) : conversation.length > 0 ? (
                <div className="space-y-2 max-h-48 overflow-y-auto">
                  <p className="text-xs text-gray-500 font-medium">Conversación previa</p>
                  {conversation.slice(0, 5).map((msg) => (
                    <div
                      key={msg.id}
                      className={`p-2 rounded-lg text-sm ${
                        msg.direction === "outbound"
                          ? "bg-purple-500/10 border border-purple-500/20 ml-4"
                          : "bg-white/5 border border-white/10 mr-4"
                      }`}
                    >
                      <p className="text-xs text-gray-500 mb-0.5">
                        {msg.direction === "outbound" ? "Nosotros" : "Cliente"}
                      </p>
                      <p className="text-gray-300 line-clamp-2">{msg.content}</p>
                    </div>
                  ))}
                </div>
              ) : null}

              {/* Tone and length selectors */}
              {!aiReply && (
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">Tono</label>
                    <select
                      value={replyTone}
                      onChange={(e) => setReplyTone(e.target.value)}
                      className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-sm text-white focus:ring-2 focus:ring-purple-500"
                    >
                      <option value="professional">Profesional</option>
                      <option value="friendly">Amigable</option>
                      <option value="assertive">Asertivo</option>
                      <option value="consultative">Consultivo</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">Longitud</label>
                    <select
                      value={replyLength}
                      onChange={(e) => setReplyLength(e.target.value)}
                      className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-sm text-white focus:ring-2 focus:ring-purple-500"
                    >
                      <option value="short">Corta</option>
                      <option value="medium">Media</option>
                      <option value="long">Larga</option>
                    </select>
                  </div>
                </div>
              )}

              {/* Generate button */}
              {!aiReply && (
                <button
                  onClick={handleGenerateReply}
                  disabled={generatingReply}
                  className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors disabled:opacity-50"
                >
                  {generatingReply ? (
                    <Loader2 className="w-5 h-5 animate-spin" />
                  ) : (
                    <Wand2 className="w-5 h-5" />
                  )}
                  {generatingReply ? "Generando respuesta..." : "Generar respuesta con IA"}
                </button>
              )}

              {/* Generated reply editor */}
              {aiReply && (
                <div className="space-y-3">
                  <div className="flex items-center gap-2">
                    <Zap className="w-4 h-4 text-purple-400" />
                    <span className="text-sm text-purple-400 font-medium">
                      Respuesta generada ({Math.round(aiReply.confidence * 100)}% confianza)
                    </span>
                    {aiReply.suggested_next_action && (
                      <span className="text-xs text-gray-500 ml-auto">
                        Siguiente paso: {aiReply.suggested_next_action}
                      </span>
                    )}
                  </div>

                  <div>
                    <label className="block text-xs text-gray-500 mb-1">Asunto</label>
                    <div className="flex items-center gap-2">
                      <input
                        type="text"
                        value={editedSubject}
                        onChange={(e) => setEditedSubject(e.target.value)}
                        className="flex-1 px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-sm text-white focus:ring-2 focus:ring-purple-500"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs text-gray-500 mb-1">Mensaje</label>
                    <textarea
                      value={editedBody}
                      onChange={(e) => setEditedBody(e.target.value)}
                      rows={12}
                      className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-sm text-white focus:ring-2 focus:ring-purple-500 resize-none"
                    />
                  </div>

                  <div className="flex items-center gap-3">
                    <button
                      onClick={handleSendReply}
                      disabled={sendingReply || !editedSubject || !editedBody}
                      className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50"
                    >
                      {sendingReply ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <Send className="w-4 h-4" />
                      )}
                      {sendingReply ? "Enviando..." : "Enviar respuesta"}
                    </button>
                    <button
                      onClick={() => {
                        setAiReply(null);
                        setEditedSubject("");
                        setEditedBody("");
                      }}
                      className="px-4 py-2 border border-white/10 text-gray-300 rounded-lg hover:bg-white/5 transition-colors text-sm"
                    >
                      Regenerar
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
