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

// Add auth token to every request
api.interceptors.request.use((config) => {
  const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
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
};

// Leads API
export const leadsApi = {
  list: (params?: { status?: string; city?: string; search?: string; page?: number; page_size?: number; lat?: number; lng?: number; sort_by?: string }) =>
    api.get("/leads", { params }),
  get: (id: number) => api.get(`/leads/${id}`),
  create: (data: any) => api.post("/leads", data),
  update: (id: number, data: any) => api.patch(`/leads/${id}`, data),
  delete: (id: number) => api.delete(`/leads/${id}`),
  enrich: (id: number) => api.post(`/leads/${id}/enrich`),
  discover: (data: any) => api.post("/leads/discover", data),
  search: (data: { query: string; limit?: number; status?: string; min_score?: number }) =>
    api.post("/leads/search", data),
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
};

// Emails API
export const emailsApi = {
  send: (leadId: number, subject: string, body: string) =>
    api.post(`/emails/${leadId}/send`, { subject, body }),
  generateAndSend: (leadId: number, context?: string) =>
    api.post(`/emails/${leadId}/generate-and-send`, { campaign_context: context }),
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
