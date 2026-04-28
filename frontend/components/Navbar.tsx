"use client";

import { useState, useEffect, useRef } from "react";
import {
  Zap,
  BarChart3,
  Users,
  Mail,
  Settings,
  GitBranch,
  LogOut,
  UserCircle,
  Calendar,
  ListOrdered,
  Inbox,
  Briefcase,
  ChevronDown,
  Menu,
  X,
  TrendingUp,
  FileText,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import { emailsApi } from "@/lib/api";

const PRIMARY_LINKS = [
  { href: "/", icon: BarChart3, label: "Dashboard" },
  { href: "/leads", icon: Users, label: "Leads" },
  { href: "/pipeline", icon: GitBranch, label: "Pipeline" },
  { href: "/deals", icon: Briefcase, label: "Deals" },
  { href: "/inbox", icon: Inbox, label: "Inbox", badgeKey: "unread" as const },
];

const MORE_LINKS = [
  { href: "/proposals", icon: FileText, label: "Propuestas" },
  { href: "/voice-agent", icon: Mic, label: "Voice Agent" },
  { href: "/sequences", icon: ListOrdered, label: "Secuencias" },
  { href: "/campaigns", icon: Mail, label: "Campañas" },
  { href: "/calendar", icon: Calendar, label: "Calendar" },
  { href: "/analytics", icon: TrendingUp, label: "Analytics" },
  { href: "/settings", icon: Settings, label: "Config" },
];

export default function Navbar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const [unreadCount, setUnreadCount] = useState(0);
  const [moreOpen, setMoreOpen] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const moreRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!user) return;
    const loadUnread = async () => {
      try {
        const res = await emailsApi.inbox({ status: "unread", limit: 1 });
        setUnreadCount(res.data?.unread_count || 0);
      } catch {
        // silently fail
      }
    };
    loadUnread();
    const interval = setInterval(loadUnread, 30000);
    return () => clearInterval(interval);
  }, [user]);

  // Close dropdown on outside click
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (moreRef.current && !moreRef.current.contains(e.target as Node)) {
        setMoreOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  // Close mobile menu on route change
  useEffect(() => {
    setMobileOpen(false);
    setMoreOpen(false);
  }, [pathname]);

  const isActive = (href: string) => {
    if (href === "/") return pathname === "/";
    return pathname.startsWith(href);
  };

  return (
    <>
      <nav className="glass fixed top-0 left-0 right-0 z-50 border-b border-white/5">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            {/* Logo */}
            <Link href="/" className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-eko-blue to-eko-blue-dark flex items-center justify-center">
                <Zap className="w-5 h-5 text-white" />
              </div>
              <span className="font-display font-bold text-lg tracking-tight">
                Eko <span className="text-eko-blue">AI</span>
              </span>
            </Link>

            {/* Desktop nav */}
            <div className="hidden lg:flex items-center gap-1">
              {PRIMARY_LINKS.map((link) => (
                <NavLink
                  key={link.href}
                  href={link.href}
                  icon={<link.icon className="w-4 h-4" />}
                  label={link.label}
                  active={isActive(link.href)}
                  badge={link.badgeKey === "unread" && unreadCount > 0 ? unreadCount : undefined}
                />
              ))}

              {/* More dropdown */}
              <div className="relative" ref={moreRef}>
                <button
                  onClick={() => setMoreOpen((v) => !v)}
                  className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors ${
                    moreOpen || MORE_LINKS.some((l) => isActive(l.href))
                      ? "text-white bg-white/10"
                      : "text-gray-400 hover:text-white hover:bg-white/5"
                  }`}
                >
                  <span>Más</span>
                  <ChevronDown className={`w-3.5 h-3.5 transition-transform ${moreOpen ? "rotate-180" : ""}`} />
                </button>

                {moreOpen && (
                  <div className="absolute right-0 mt-2 w-52 rounded-xl border border-white/10 bg-eko-graphite shadow-xl overflow-hidden z-50">
                    {MORE_LINKS.map((link) => (
                      <Link
                        key={link.href}
                        href={link.href}
                        className={`flex items-center gap-3 px-4 py-2.5 text-sm transition-colors ${
                          isActive(link.href)
                            ? "text-white bg-white/10"
                            : "text-gray-400 hover:text-white hover:bg-white/5"
                        }`}
                      >
                        <link.icon className="w-4 h-4" />
                        <span>{link.label}</span>
                      </Link>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Right side */}
            <div className="flex items-center gap-3">
              {user ? (
                <>
                  <div className="hidden sm:flex items-center gap-2 text-sm text-gray-400">
                    <UserCircle className="w-4 h-4" />
                    <span className="max-w-[120px] truncate">{user.full_name || user.email}</span>
                    <span className="text-xs px-1.5 py-0.5 rounded bg-white/10 text-gray-500 capitalize">
                      {user.role}
                    </span>
                  </div>
                  <button
                    onClick={logout}
                    className="p-2 rounded-lg text-gray-400 hover:text-white hover:bg-white/10 transition-colors"
                    title="Logout"
                  >
                    <LogOut className="w-4 h-4" />
                  </button>
                </>
              ) : (
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-eko-green animate-pulse" />
                  <span className="text-xs text-gray-400">System Online</span>
                </div>
              )}

              {/* Mobile hamburger */}
              <button
                onClick={() => setMobileOpen((v) => !v)}
                className="lg:hidden p-2 rounded-lg text-gray-400 hover:text-white hover:bg-white/10 transition-colors"
              >
                {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
              </button>
            </div>
          </div>
        </div>
      </nav>

      {/* Mobile menu overlay */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-black/50" onClick={() => setMobileOpen(false)} />
          <div className="absolute top-16 left-0 right-0 bg-eko-graphite border-b border-white/10 shadow-xl">
            <div className="px-4 py-3 space-y-1">
              {[...PRIMARY_LINKS, ...MORE_LINKS].map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                    isActive(link.href)
                      ? "text-white bg-white/10"
                      : "text-gray-400 hover:text-white hover:bg-white/5"
                  }`}
                >
                  <link.icon className="w-4 h-4" />
                  <span>{link.label}</span>
                  {(link as any).badgeKey === "unread" && unreadCount > 0 && (
                    <span className="ml-auto flex items-center justify-center min-w-[18px] h-[18px] px-1 rounded-full bg-red-500 text-white text-[10px] font-bold">
                      {unreadCount > 99 ? "99+" : unreadCount}
                    </span>
                  )}
                </Link>
              ))}
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function NavLink({
  href,
  icon,
  label,
  active,
  badge,
}: {
  href: string;
  icon: React.ReactNode;
  label: string;
  active: boolean;
  badge?: number;
}) {
  return (
    <Link
      href={href}
      className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors ${
        active ? "text-white bg-white/10" : "text-gray-400 hover:text-white hover:bg-white/5"
      }`}
    >
      {icon}
      <span>{label}</span>
      {badge !== undefined && badge > 0 && (
        <span className="flex items-center justify-center min-w-[18px] h-[18px] px-1 rounded-full bg-red-500 text-white text-[10px] font-bold">
          {badge > 99 ? "99+" : badge}
        </span>
      )}
    </Link>
  );
}
