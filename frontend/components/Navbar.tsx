"use client";

import { Zap, BarChart3, Users, Mail, Settings, GitBranch, LogOut, UserCircle, Calendar } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";

export default function Navbar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  return (
    <nav className="glass fixed top-0 left-0 right-0 z-50 border-b border-white/5">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-eko-blue to-eko-blue-dark flex items-center justify-center">
              <Zap className="w-5 h-5 text-white" />
            </div>
            <span className="font-display font-bold text-lg tracking-tight">
              Eko <span className="text-eko-blue">AI</span>
            </span>
          </div>
          
          <div className="hidden md:flex items-center gap-1">
            <NavLink href="/" icon={<BarChart3 className="w-4 h-4" />} label="Dashboard" active={pathname === "/"} />
            <NavLink href="/leads" icon={<Users className="w-4 h-4" />} label="Leads" active={pathname.startsWith("/leads")} />
            <NavLink href="/pipeline" icon={<GitBranch className="w-4 h-4" />} label="Pipeline" active={pathname === "/pipeline"} />
            <NavLink href="/campaigns" icon={<Mail className="w-4 h-4" />} label="Campañas" active={pathname === "/campaigns"} />
            <NavLink href="/calendar" icon={<Calendar className="w-4 h-4" />} label="Calendar" active={pathname === "/calendar"} />
            <NavLink href="/settings" icon={<Settings className="w-4 h-4" />} label="Config" active={pathname === "/settings"} />
          </div>
          
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
          </div>
        </div>
      </div>
    </nav>
  );
}

function NavLink({ href, icon, label, active }: { href: string; icon: React.ReactNode; label: string; active: boolean }) {
  return (
    <Link
      href={href}
      className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors ${
        active
          ? "text-white bg-white/10"
          : "text-gray-400 hover:text-white hover:bg-white/5"
      }`}
    >
      {icon}
      <span>{label}</span>
    </Link>
  );
}
