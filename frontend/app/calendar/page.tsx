"use client";

import { useState, useEffect } from "react";
import {
  Calendar as CalendarIcon,
  Clock,
  Video,
  MapPin,
  Phone,
  X,
  CheckCircle,
  AlertCircle,
  Loader2,
  User,
  Mail,
} from "lucide-react";
import Navbar from "@/components/Navbar";
import { calendarApi } from "@/lib/api";

interface Booking {
  id: number;
  title: string;
  start_time: string;
  end_time: string | null;
  status: string;
  attendee_name: string;
  attendee_email: string;
  location: string | null;
  location_type: string | null;
  notes: string | null;
  lead_id: number;
}

export default function CalendarPage() {
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [filter, setFilter] = useState<"upcoming" | "all" | "past">("upcoming");
  const [cancellingId, setCancellingId] = useState<number | null>(null);

  useEffect(() => {
    loadBookings();
  }, [filter]);

  const loadBookings = async () => {
    setIsLoading(true);
    try {
      const params: any = {};
      if (filter === "upcoming") params.upcoming = true;
      const res = await calendarApi.listBookings(params);
      setBookings(res.data);
    } catch (err) {
      console.error("Failed to load bookings:", err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCancel = async (id: number) => {
    if (!confirm("Cancel this meeting?")) return;
    setCancellingId(id);
    try {
      await calendarApi.cancelBooking(id, "Cancelled by user");
      await loadBookings();
    } catch (err) {
      console.error("Failed to cancel:", err);
    } finally {
      setCancellingId(null);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "confirmed":
        return "bg-green-500/10 text-green-400 border-green-500/20";
      case "pending":
        return "bg-yellow-500/10 text-yellow-400 border-yellow-500/20";
      case "cancelled":
        return "bg-red-500/10 text-red-400 border-red-500/20";
      case "completed":
        return "bg-blue-500/10 text-blue-400 border-blue-500/20";
      default:
        return "bg-gray-500/10 text-gray-400 border-gray-500/20";
    }
  };

  const getLocationIcon = (type: string | null) => {
    switch (type) {
      case "video":
        return <Video className="w-4 h-4" />;
      case "phone":
        return <Phone className="w-4 h-4" />;
      case "in_person":
        return <MapPin className="w-4 h-4" />;
      default:
        return <Video className="w-4 h-4" />;
    }
  };

  const formatDate = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleDateString("en-US", {
      weekday: "short",
      month: "short",
      day: "numeric",
    });
  };

  const formatTime = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleTimeString("en-US", {
      hour: "numeric",
      minute: "2-digit",
    });
  };

  return (
    <div className="min-h-screen bg-eko-graphite">
      <Navbar />

      <main className="pt-20 pb-12 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold font-display">Calendar</h1>
            <p className="text-gray-400 text-sm mt-1">
              Meetings and appointments
            </p>
          </div>

          {/* Filter tabs */}
          <div className="flex items-center gap-1 bg-white/5 rounded-lg p-1">
            {(["upcoming", "all", "past"] as const).map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-3 py-1.5 rounded-md text-sm capitalize transition-colors ${
                  filter === f
                    ? "bg-white/10 text-white"
                    : "text-gray-400 hover:text-white"
                }`}
              >
                {f}
              </button>
            ))}
          </div>
        </div>

        {/* Bookings list */}
        {isLoading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-8 h-8 animate-spin text-eko-blue" />
          </div>
        ) : bookings.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-gray-500">
            <CalendarIcon className="w-12 h-12 mb-4 opacity-50" />
            <p className="text-lg font-medium">No meetings found</p>
            <p className="text-sm">
              {filter === "upcoming"
                ? "No upcoming meetings scheduled"
                : "No meetings match this filter"}
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {bookings.map((booking) => (
              <div
                key={booking.id}
                className="rounded-xl border border-white/10 bg-white/5 p-5 hover:border-white/20 transition-colors"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <h3 className="font-semibold text-white">
                        {booking.title}
                      </h3>
                      <span
                        className={`px-2 py-0.5 rounded-full text-xs border capitalize ${getStatusColor(
                          booking.status
                        )}`}
                      >
                        {booking.status}
                      </span>
                    </div>

                    <div className="flex flex-wrap items-center gap-4 text-sm text-gray-400">
                      <div className="flex items-center gap-1.5">
                        <CalendarIcon className="w-4 h-4" />
                        <span>{formatDate(booking.start_time)}</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <Clock className="w-4 h-4" />
                        <span>
                          {formatTime(booking.start_time)}
                          {booking.end_time &&
                            ` - ${formatTime(booking.end_time)}`}
                        </span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        {getLocationIcon(booking.location_type)}
                        <span className="capitalize">
                          {booking.location_type || "Video"}
                        </span>
                      </div>
                    </div>

                    <div className="flex items-center gap-4 mt-3 text-sm">
                      <div className="flex items-center gap-1.5 text-gray-400">
                        <User className="w-4 h-4" />
                        <span>{booking.attendee_name}</span>
                      </div>
                      <div className="flex items-center gap-1.5 text-gray-400">
                        <Mail className="w-4 h-4" />
                        <span>{booking.attendee_email}</span>
                      </div>
                    </div>

                    {booking.notes && (
                      <p className="mt-2 text-sm text-gray-500">
                        {booking.notes}
                      </p>
                    )}

                    {booking.location && booking.status !== "cancelled" && (
                      <a
                        href={booking.location}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1.5 mt-3 text-sm text-eko-blue hover:text-eko-blue-dark"
                      >
                        <CheckCircle className="w-4 h-4" />
                        Join meeting
                      </a>
                    )}
                  </div>

                  {booking.status !== "cancelled" &&
                    booking.status !== "completed" && (
                      <button
                        onClick={() => handleCancel(booking.id)}
                        disabled={cancellingId === booking.id}
                        className="p-2 rounded-lg text-gray-400 hover:text-red-400 hover:bg-red-500/10 transition-colors disabled:opacity-50"
                        title="Cancel meeting"
                      >
                        {cancellingId === booking.id ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <X className="w-4 h-4" />
                        )}
                      </button>
                    )}
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
