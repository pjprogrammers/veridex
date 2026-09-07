"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Activity,
  Bell,
  Database,
  LayoutDashboard,
  Menu,
  ScanLine,
  ScrollText,
  ShieldCheck,
  X,
} from "lucide-react";
import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";
import { useSystemStatus } from "@/lib/system";
import type { LucideIcon } from "lucide-react";

interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

const NAV: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/verify", label: "New Verification", icon: ScanLine },
  { href: "/cases", label: "Cases", icon: ScrollText },
  { href: "/registry", label: "Registry", icon: Database },
  { href: "/audit", label: "Audit Trail", icon: Activity },
  { href: "/system", label: "System Health", icon: ShieldCheck },
];

function VeridexMark() {
  return (
    <div className="flex items-center gap-3">
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-indigo-600 text-sm font-bold text-white">
        V
      </div>
      <div>
        <div className="text-sm font-semibold text-white">VERIDEX</div>
        <div className="text-[10px] text-slate-500">Officer Console</div>
      </div>
    </div>
  );
}

function SidebarContent({
  onNavigate,
}: {
  onNavigate?: () => void;
}) {
  const pathname = usePathname();
  return (
    <>
      <div className="px-5 py-5">
        <VeridexMark />
      </div>
      <nav
        aria-label="Primary"
        className="mt-2 flex-1 space-y-1 px-3"
      >
        {NAV.map((item) => {
          const active =
            item.href === "/dashboard"
              ? pathname === "/dashboard"
              : item.href === "/verify"
                ? pathname === "/verify" || pathname.startsWith("/verify/")
                : pathname.startsWith(item.href);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={onNavigate}
              aria-current={active ? "page" : undefined}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                active
                  ? "bg-slate-800 text-white"
                  : "text-slate-400 hover:bg-slate-900 hover:text-white",
              )}
            >
              <Icon className="h-4 w-4 shrink-0" strokeWidth={2} aria-hidden />
              <span className="truncate">{item.label}</span>
            </Link>
          );
        })}
      </nav>
      <div className="px-5 py-4 text-[10px] leading-4 text-slate-600">
        Decision-support only. AI results never prove fraud; manual review is
        required.
      </div>
    </>
  );
}

export default function ConsoleShell({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user, loading, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const system = useSystemStatus();

  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (!loading && !user) {
      router.replace("/login");
    }
  }, [loading, user, router]);

  if (loading || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-100">
        <div className="text-sm text-slate-500" role="status">
          Loading…
        </div>
      </div>
    );
  }

  const statusLabel = system?.status === "ok" ? "All systems operational" : "Systems degraded";

  return (
    <div className="flex min-h-screen bg-slate-100">
      {/* Desktop sidebar */}
      <aside className="hidden w-60 shrink-0 flex-col border-r border-slate-800 bg-slate-950 text-slate-300 lg:flex">
        <SidebarContent />
      </aside>

      {/* Mobile drawer */}
      {mobileOpen ? (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div
            className="absolute inset-0 bg-slate-950/60"
            onClick={() => setMobileOpen(false)}
            aria-hidden
          />
          <aside className="absolute inset-y-0 left-0 flex w-64 flex-col border-r border-slate-800 bg-slate-950 text-slate-300 shadow-2xl">
            <div className="flex items-center justify-between pl-1 pr-3">
              <SidebarContent onNavigate={() => setMobileOpen(false)} />
              <button
                onClick={() => setMobileOpen(false)}
                aria-label="Close navigation"
                className="absolute right-3 top-5 rounded-lg p-1.5 text-slate-400 hover:bg-slate-800"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
          </aside>
        </div>
      ) : null}

      <div className="flex min-w-0 flex-1 flex-col">
        {/* Top bar */}
        <header className="sticky top-0 z-30 flex h-16 items-center justify-between gap-4 border-b border-slate-200 bg-white px-4 sm:px-6">
          <div className="flex items-center gap-3">
            <button
              className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 lg:hidden"
              onClick={() => setMobileOpen(true)}
              aria-label="Open navigation"
            >
              <Menu className="h-5 w-5" />
            </button>
            <div className="flex items-center gap-2 lg:hidden">
              <span className="text-sm font-bold text-slate-900">VERIDEX</span>
            </div>
          </div>

          <div className="flex items-center gap-3 sm:gap-5">
            {/* System status */}
            <div
              className={cn(
                "hidden items-center gap-2 rounded-full px-3 py-1 text-xs font-medium ring-1 ring-inset sm:inline-flex",
                system?.status === "ok"
                  ? "bg-emerald-50 text-emerald-700 ring-emerald-600/20"
                  : system
                    ? "bg-amber-50 text-amber-700 ring-amber-600/20"
                    : "bg-slate-100 text-slate-600 ring-slate-500/20",
              )}
              title={statusLabel}
            >
              <span
                className={cn(
                  "h-2 w-2 rounded-full",
                  system?.status === "ok"
                    ? "bg-emerald-500"
                    : system
                      ? "bg-amber-500"
                      : "bg-slate-400",
                )}
                aria-hidden
              />
              {statusLabel}
            </div>

            {/* Notification indicator */}
            <button
              className="relative rounded-lg p-2 text-slate-500 hover:bg-slate-100"
              aria-label="Notifications"
            >
              <Bell className="h-5 w-5" aria-hidden />
              <span className="absolute right-1.5 top-1.5 flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-red-400 opacity-75" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-red-500" />
              </span>
            </button>

            {/* Officer identity */}
            <div className="flex items-center gap-3 border-l border-slate-200 pl-4">
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-indigo-100 text-sm font-bold capitalize text-indigo-700" aria-hidden>
                {(user.full_name || user.username).charAt(0)}
              </div>
              <div className="hidden text-right sm:block">
                <div className="text-sm font-medium text-slate-900">
                  {user.full_name || user.username}
                </div>
                <div className="text-xs capitalize text-slate-500">
                  {user.role}
                </div>
              </div>
              <button
                onClick={logout}
                className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50"
              >
                Sign out
              </button>
            </div>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto p-4 sm:p-6">{children}</main>
      </div>
    </div>
  );
}
