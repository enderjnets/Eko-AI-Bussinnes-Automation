import axios from "axios";

// In browser: use relative paths so requests go through Next.js rewrites
// (avoids CORS and cross-network issues, e.g. Tailscale users)
// In SSR/server: use the full API URL
const API_URL =
  typeof window !== "undefined"
    ? ""
    : (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000");

export const api = axios.create({
  baseURL: `${API_URL}/api/v1`,
  headers: {
    "Content-Type": "application/json",
  },
});

// Add auth token and workspace header to every request
api.interceptors.request.use((config) => {
  const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  const workspaceId = typeof window !== "undefined" ? localStorage.getItem("workspace_id") : null;
  if (workspaceId) {
    config.headers["X-Workspace-ID"] = workspaceId;
  }
  return config;
});

// Handle 401 globally
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && typeof window !== "undefined") {
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

// Auth API
export const authApi = {
  login: (email: string, password: string) =>
    api.post("/auth/login", { email, password }),
  devLogin: () =>
    api.post("/auth/dev-login"),
  me: () =>
    api.get("/auth/me"),
  refresh: (refreshToken: string) =>
    api.post("/auth/refresh", { refresh_token: refreshToken }),
  updateMe: (data: { full_name?: string; email?: string; password?: string }) =>
    api.patch("/auth/me", data),
};

// Leads API
export const leadsApi = {
  list: (params?: { status?: string; city?: string; search?: string; page?: number; page_size?: number; lat?: number; lng?: number; sort_by?: string; min_score?: number; max_score?: number; has_email?: boolean; has_phone?: boolean; has_website?: boolean; category?: string }) =>
    api.get("/leads", { params }),
  get: (id: number) => api.get(`/leads/${id}`),
  create: (data: any) => api.post("/leads", data),
  update: (id: number, data: any) => api.patch(`/leads/${id}`, data),
  delete: (id: number) => api.delete(`/leads/${id}`),
  enrich: (id: number) => api.post(`/leads/${id}/enrich`),
  discover: (data: any) => api.post("/leads/discover", data),
  search: (data: { query: string; limit?: number; status?: string; min_score?: number }) =>
    api.post("/leads/search", data),
  autocomplete: (q: string, limit?: number) =>
    api.get("/leads/autocomplete/names", { params: { q, limit } }),
  bulkContact: (leadIds: number[], template?: string, customSubject?: string, customBody?: string) =>
    api.post("/leads/bulk/contact", { lead_ids: leadIds, template, custom_subject: customSubject, custom_body: customBody }),
};

// CRM API
export const crmApi = {
  transition: (id: number, new_status: string, note?: string) =>
    api.post(`/crm/${id}/transition`, null, { params: { new_status, note } }),
  contact: (id: number, channel: string, template?: string, custom_subject?: string, custom_body?: string) =>
    api.post(`/crm/${id}/contact`, null, { params: { channel, template, custom_subject, custom_body } }),
  scheduleFollowUp: (id: number, days: number, note?: string) =>
    api.post(`/crm/${id}/schedule-follow-up`, null, { params: { days, note } }),
  getPipelineSummary: () => api.get("/crm/pipeline/summary"),
  getPendingFollowUps: (limit?: number) => api.get("/crm/follow-ups", { params: { limit } }),
};

// Campaigns API
export const campaignsApi = {
  list: () => api.get("/campaigns"),
  get: (id: number) => api.get(`/campaigns/${id}`),
  create: (data: any) => api.post("/campaigns", data),
  update: (id: number, data: any) => api.patch(`/campaigns/${id}`, data),
  launch: (id: number) => api.post(`/campaigns/${id}/launch`),
  pause: (id: number) => api.post(`/campaigns/${id}/pause`),
};

// Analytics API
export const analyticsApi = {
  pipeline: () => api.get("/analytics/pipeline"),
  performance: () => api.get("/analytics/performance"),
  campaign: (id: number) => api.get(`/analytics/campaigns/${id}`),
};

// Emails API
export const emailsApi = {
  send: (leadId: number, subject: string, body: string) =>
    api.post(`/emails/${leadId}/send`, { subject, body }),
  generateAndSend: (leadId: number, context?: string) =>
    api.post(`/emails/${leadId}/generate-and-send`, { campaign_context: context }),
  inbox: (params?: { status?: string; direction?: string; lead_id?: number; limit?: number; offset?: number }) =>
    api.get("/emails/inbox", { params }),
  replyManual: (interactionId: number, data: { subject: string; body: string }) =>
    api.post(`/emails/${interactionId}/reply-manual`, data),
  markRead: (interactionId: number) =>
    api.post(`/emails/${interactionId}/mark-read`),
  simulateReply: (leadId: number, subject: string, body: string, fromEmail?: string) =>
    api.post("/emails/simulate-reply", { lead_id: leadId, subject, body, from_email: fromEmail }),
  aiReply: (interactionId: number, data: { tone?: string; max_length?: string; custom_instructions?: string }) =>
    api.post(`/emails/${interactionId}/ai-reply`, data),
  sendReply: (interactionId: number, data: { subject: string; body: string; send_email?: boolean }) =>
    api.post(`/emails/${interactionId}/send-reply`, data),
  conversation: (interactionId: number) =>
    api.get(`/emails/${interactionId}/conversation`),
  delete: (interactionId: number) =>
    api.delete(`/emails/${interactionId}`),
  bulkDelete: (ids: number[]) =>
    api.delete("/emails/bulk/delete", { data: { ids } }),
  forward: (interactionId: number, data: { to_email: string; note?: string }) =>
    api.post(`/emails/${interactionId}/forward`, data),
  createDraft: (data: { lead_id: number; subject: string; body: string }) =>
    api.post("/emails/drafts", data),
  updateDraft: (draftId: number, data: { subject?: string; body?: string }) =>
    api.patch(`/emails/drafts/${draftId}`, data),
  sendDraft: (draftId: number) =>
    api.post(`/emails/drafts/${draftId}/send`),
  deleteDraft: (draftId: number) =>
    api.delete(`/emails/drafts/${draftId}`),
};

// Sequences API
export const sequencesApi = {
  list: (status?: string) => api.get("/sequences", { params: { status } }),
  get: (id: number) => api.get(`/sequences/${id}`),
  create: (data: any) => api.post("/sequences", data),
  update: (id: number, data: any) => api.patch(`/sequences/${id}`, data),
  addStep: (id: number, data: any) => api.post(`/sequences/${id}/steps`, data),
  deleteStep: (sequenceId: number, stepId: number) => api.delete(`/sequences/${sequenceId}/steps/${stepId}`),
  enroll: (id: number, leadIds: number[]) => api.post(`/sequences/${id}/enroll`, leadIds),
  execute: (id: number, leadIds: number[], dryRun?: boolean) => api.post(`/sequences/${id}/execute`, { lead_ids: leadIds, dry_run: dryRun ?? false }),
};

// Phone Calls API
export const phoneCallsApi = {
  create: (data: { lead_id: number; result: string; notes?: string; interest_level?: string; next_action?: string; call_duration_seconds?: number; scheduled_at?: string }) =>
    api.post("/phone-calls", data),
  scheduled: () => api.get("/phone-calls/scheduled"),
  byLead: (leadId: number) => api.get(`/phone-calls/lead/${leadId}`),
};

// Settings API
export const settingsApi = {
  list: (category?: string) => api.get("/settings", { params: { category } }),
  get: (key: string) => api.get(`/settings/${key}`),
  create: (data: any) => api.post("/settings", data),
  update: (key: string, data: any) => api.patch(`/settings/${key}`, data),
  bulkUpdate: (settings: Record<string, string>, category?: string) =>
    api.post("/settings/bulk", { settings, category }),
  delete: (key: string) => api.delete(`/settings/${key}`),
};

// Deals API
export const dealsApi = {
  list: (params?: { status?: string; lead_id?: number; min_value?: number; max_value?: number; assigned_to?: string; limit?: number; offset?: number }) =>
    api.get("/deals", { params }),
  get: (id: number) => api.get(`/deals/${id}`),
  create: (data: any) => api.post("/deals", data),
  update: (id: number, data: any) => api.patch(`/deals/${id}`, data),
  delete: (id: number) => api.delete(`/deals/${id}`),
  byLead: (leadId: number) => api.get(`/deals/lead/${leadId}/deals`),
  forecast: () => api.get("/deals/forecast/revenue"),
};

// Proposals API
export const proposalsApi = {
  list: (params?: { status?: string; deal_id?: number; search?: string; limit?: number; offset?: number }) =>
    api.get("/proposals", { params }),
  get: (id: number) => api.get(`/proposals/${id}`),
  create: (data: any) => api.post("/proposals", data),
  update: (id: number, data: any) => api.patch(`/proposals/${id}`, data),
  delete: (id: number) => api.delete(`/proposals/${id}`),
  generate: (id: number, data?: any) => api.post(`/proposals/${id}/generate`, data || {}),
  send: (id: number) => api.post(`/proposals/${id}/send`),
  duplicate: (id: number) => api.post(`/proposals/${id}/duplicate`),
  public: (token: string) => api.get(`/proposals/public/${token}`),
  accept: (token: string) => api.post(`/proposals/public/${token}/accept`),
  reject: (token: string, feedback?: string) => api.post(`/proposals/public/${token}/reject`, null, { params: { feedback } }),
};

// Voice Agent API
export const voiceAgentApi = {
  startCall: (data: { lead_id: number; assistant_id?: string; first_message?: string; custom_instructions?: string; schedule_now?: boolean }) =>
    api.post("/voice-agent/calls", data),
  listCalls: (params?: { lead_id?: number; status?: string; limit?: number; offset?: number }) =>
    api.get("/voice-agent/calls", { params }),
  getCall: (id: number) => api.get(`/voice-agent/calls/${id}`),
  createAssistant: (data: { name: string; system_prompt?: string; first_message?: string; voice_provider?: string; voice_id?: string; model?: string }) =>
    api.post("/voice-agent/assistants", data),
  updateAssistant: (id: string, data: { name?: string; system_prompt?: string; first_message?: string; voice_id?: string }) =>
    api.patch(`/voice-agent/assistants/${id}`, data),
  getConfig: () => api.get("/voice-agent/config"),
};

// Calendar API
export const calendarApi = {
  eventTypes: () => api.get("/calendar/event-types"),
  availability: (data: { event_type_id: number; start_date: string; end_date: string }) =>
    api.post("/calendar/availability", data),
  listBookings: (params?: { status?: string; lead_id?: number; upcoming?: boolean }) =>
    api.get("/calendar/bookings", { params }),
  createBooking: (data: any) => api.post("/calendar/bookings", data),
  cancelBooking: (id: number, reason?: string) =>
    api.post(`/calendar/bookings/${id}/cancel`, null, { params: { reason } }),
  sendLink: (data: { lead_id: number; event_type_id?: number; message?: string }) =>
    api.post("/calendar/send-link", data),
};

// ─────────────────────────────────────────────────────────────
// Metadata Engine API
// ─────────────────────────────────────────────────────────────

export interface FieldMetadata {
  id: string;
  object_metadata_id: string;
  workspace_id?: string;
  name: string;
  label: string;
  type: string;
  description?: string;
  icon?: string;
  default_value?: any;
  options?: { label: string; value: string; color?: string }[];
  settings?: Record<string, any>;
  is_custom: boolean;
  is_system: boolean;
  is_active: boolean;
  is_nullable: boolean;
  is_unique: boolean;
  is_read_only: boolean;
  is_label_field: boolean;
  position: number;
  relation_target_object_id?: string;
  relation_target_field_id?: string;
  created_at: string;
  updated_at: string;
}

export interface ObjectMetadata {
  id: string;
  workspace_id?: string;
  name_singular: string;
  name_plural: string;
  label_singular: string;
  label_plural: string;
  description?: string;
  icon?: string;
  color?: string;
  target_table_name?: string;
  is_custom: boolean;
  is_system: boolean;
  is_active: boolean;
  is_searchable: boolean;
  position: number;
  duplicate_criteria?: string[];
  fields: FieldMetadata[];
  created_at: string;
  updated_at: string;
}

export interface ViewField {
  id: string;
  view_id: string;
  field_metadata_id: string;
  position: number;
  is_visible: boolean;
  width?: number;
}

export interface ViewFilter {
  id: string;
  view_id: string;
  field_metadata_id: string;
  operator: string;
  value?: Record<string, any>;
  display_value?: string;
}

export interface ViewSort {
  id: string;
  view_id: string;
  field_metadata_id: string;
  direction: "asc" | "desc";
}

export interface View {
  id: string;
  workspace_id?: string;
  object_metadata_id: string;
  name: string;
  type: "table" | "kanban" | "calendar" | "gallery";
  icon: string;
  position: number;
  is_default: boolean;
  is_compact: boolean;
  is_system: boolean;
  group_by_field_id?: string;
  calendar_field_id?: string;
  visibility: string;
  created_by_user_id?: number;
  view_fields: ViewField[];
  view_filters: ViewFilter[];
  view_sorts: ViewSort[];
  created_at: string;
  updated_at: string;
}

export interface DynamicRecord {
  id: string;
  workspace_id?: string;
  object_metadata_id: string;
  label: string;
  data: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export const metadataApi = {
  listObjects: () => api.get<{ total: number; items: ObjectMetadata[] }>("/metadata/objects"),
  getObject: (id: string) => api.get<ObjectMetadata>(`/metadata/objects/${id}`),
  getObjectByName: (name: string) => api.get<ObjectMetadata>(`/metadata/objects/by-name/${name}`),
  createObject: (data: any) => api.post<ObjectMetadata>("/metadata/objects", data),
  updateObject: (id: string, data: any) => api.patch<ObjectMetadata>(`/metadata/objects/${id}`, data),
  deleteObject: (id: string) => api.delete(`/metadata/objects/${id}`),

  listFields: (objectId?: string) =>
    api.get<{ total: number; items: FieldMetadata[] }>("/metadata/fields", { params: objectId ? { object_metadata_id: objectId } : undefined }),
  createField: (data: any) => api.post<FieldMetadata>("/metadata/fields", data),
  updateField: (id: string, data: any) => api.patch<FieldMetadata>(`/metadata/fields/${id}`, data),
  deleteField: (id: string) => api.delete(`/metadata/fields/${id}`),
};

export const viewsApi = {
  list: (objectMetadataId?: string) =>
    api.get<{ total: number; items: View[] }>("/views", { params: objectMetadataId ? { object_metadata_id: objectMetadataId } : undefined }),
  get: (id: string) => api.get<View>(`/views/${id}`),
  create: (data: any) => api.post<View>("/views", data),
  update: (id: string, data: any) => api.patch<View>(`/views/${id}`, data),
  delete: (id: string) => api.delete(`/views/${id}`),
};

export const dynamicDataApi = {
  list: (objectName: string, params?: { search?: string; limit?: number; offset?: number; filters?: Record<string, any>; sorts?: { field: string; direction: string }[] }) =>
    api.get<{ total: number; items: DynamicRecord[] }>(`/data/${objectName}`, { params }),
  get: (objectName: string, recordId: string) =>
    api.get<DynamicRecord>(`/data/${objectName}/${recordId}`),
  create: (objectName: string, data: { label: string; data: Record<string, any> }) =>
    api.post<DynamicRecord>(`/data/${objectName}`, data),
  update: (objectName: string, recordId: string, data: { label?: string; data?: Record<string, any> }) =>
    api.patch<DynamicRecord>(`/data/${objectName}/${recordId}`, data),
  delete: (objectName: string, recordId: string) =>
    api.delete(`/data/${objectName}/${recordId}`),
  enrich: (objectName: string, recordId: string) =>
    api.post<DynamicRecord>(`/data/${objectName}/${recordId}/enrich`),
};
