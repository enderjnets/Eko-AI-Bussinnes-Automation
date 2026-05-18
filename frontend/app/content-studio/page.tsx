"use client";

import { useState } from "react";
import Navbar from "@/components/Navbar";
import PipelineHistory from "@/components/content-studio/PipelineHistory";
import BufferStatus from "@/components/content-studio/BufferStatus";
import PostsList from "@/components/content-studio/PostsList";
import PostCalendar from "@/components/content-studio/PostCalendar";
import AnalyticsDashboard from "@/components/content-studio/AnalyticsDashboard";
import RunPipelinePanel from "@/components/content-studio/RunPipelinePanel";
import VideosList from "@/components/content-studio/VideosList";
import {
  Play,
  Activity,
  BarChart3,
  Clapperboard,
  FileText,
  Calendar,
  Video,
} from "lucide-react";

const TABS = [
  { id: "control", label: "Control", icon: Play },
  { id: "videos", label: "Videos", icon: Video },
  { id: "posts", label: "Publicaciones", icon: FileText },
  { id: "calendar", label: "Calendario", icon: Calendar },
  { id: "analytics", label: "Analytics", icon: BarChart3 },
  { id: "monitor", label: "Monitoreo", icon: Activity },
];

export default function ContentStudioPage() {
  const [activeTab, setActiveTab] = useState("posts");

  return (
    <div className="min-h-screen bg-eko-graphite">
      <Navbar />

      <main className="pt-20 pb-12 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 rounded-lg bg-pink-500/10 text-pink-400">
              <Clapperboard className="w-5 h-5" />
            </div>
            <h1 className="text-2xl font-bold font-display">
              Content Studio
            </h1>
          </div>
          <p className="text-gray-400 text-sm">
            Pipeline de producción de contenido para TikTok, Instagram y
            Facebook
          </p>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 mb-6 border-b border-white/5 pb-1 overflow-x-auto">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-2.5 rounded-t-lg text-sm font-medium transition-colors whitespace-nowrap ${
                activeTab === tab.id
                  ? "text-white bg-white/5 border-b-2 border-pink-400"
                  : "text-gray-500 hover:text-gray-300 hover:bg-white/[0.02]"
              }`}
            >
              <tab.icon className="w-4 h-4" />
              {tab.label}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="min-h-[400px]">
          {activeTab === "control" && <ControlTab />}
          {activeTab === "videos" && <VideosTab />}
          {activeTab === "posts" && <PostsTab />}
          {activeTab === "calendar" && <CalendarTab />}
          {activeTab === "analytics" && <AnalyticsTab />}
          {activeTab === "monitor" && <MonitorTab />}
        </div>
      </main>
    </div>
  );
}

function ControlTab() {
  return <RunPipelinePanel />;
}

function VideosTab() {
  return (
    <div className="space-y-4">
      <VideosList />
    </div>
  );
}

function PostsTab() {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-gray-400">Posts en Buffer</h3>
        <span className="text-xs text-gray-500">Gestiona publicaciones en todas las plataformas</span>
      </div>
      <PostsList />
    </div>
  );
}

function CalendarTab() {
  return (
    <div className="space-y-4">
      <PostCalendar />
    </div>
  );
}

function AnalyticsTab() {
  return (
    <div className="space-y-4">
      <AnalyticsDashboard />
    </div>
  );
}

function MonitorTab() {
  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-sm font-medium text-gray-400 mb-3">
          Estado de canales (Buffer)
        </h3>
        <BufferStatus />
      </div>

      <div>
        <h3 className="text-sm font-medium text-gray-400 mb-3">
          Historial de pipelines
        </h3>
        <PipelineHistory />
      </div>
    </div>
  );
}
