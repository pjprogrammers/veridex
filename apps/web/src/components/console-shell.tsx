"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Activity,
  Bell,
  BrainCircuit,
  Database,
  LayoutDashboard,
  LogOut,
  Menu,
  ScanLine,
  ScrollText,
  Search,
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
  { href: "/showcase", label: "AI Showcase", icon: BrainCircuit },
  { href: "/registry", label: "Registry", icon: Database },
  { href: "/audit", label: "Audit Trail", icon: Activity },
  { href: "/system", label: "System Health", icon: ShieldCheck },
];

function VeridexMark() {
  return (
    <div className="flex items-center gap-2 px-1">
      <div className="logo-badge" />
      <span className="text-base font-bold text-[var(--text)]">VERIDEX</span>
    </div>
  );
}

function NavItemLink({
  item,
  active,
  onNavigate,
}: {
  item: NavItem;
  active: boolean;
  onNavigate?: () => void;
}) {
  const Icon = item.icon;
  return (
    <Link
      href={item.href}
      onClick={onNavigate}
      aria-current={active ? "page" : undefined}
      className={cn(
        "micro-press flex items-center gap-2.5 rounded-lg px-2.5 py-2.5 text-[13px] font-medium transition-colors",
        active
          ? "bg-[var(--dark)] text-white"
          : "text-neutral-500 hover:bg-neutral-100 hover:text-neutral-800",
      )}
    >
      <Icon className="h-4 w-4 shrink-0" strokeWidth={2} aria-hidden />
      <span className="truncate">{item.label}</span>
    </Link>
  );
}

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  return (
    <>
      <div className="px-4 py-5">
        <VeridexMark />
      </div>
      <nav aria-label="Primary" className="mt-2 flex-1 space-y-0.5 px-3">
        {NAV.map((item) => {
          const active =
            item.href === "/dashboard"
              ? pathname === "/dashboard"
              : item.href === "/verify"
                ? pathname === "/verify" || pathname.startsWith("/verify/")
                : pathname.startsWith(item.href);
          return (
            <NavItemLink
              key={item.href}
              item={item}
              active={active}
              onNavigate={onNavigate}
            />
          );
        })}
      </nav>

      <div className="mx-3 mb-3 rounded-xl border border-[var(--border)] bg-[var(--card)] p-3">
        <p className="text-[11px] leading-4 text-[var(--muted)]">
          Decision-support only. AI results never prove fraud; manual review is
          required.
        </p>
      </div>

      <div className="border-t border-[var(--border)] px-3 py-2">
        <button
          onClick={onNavigate}
          className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2.5 text-[13px] font-medium text-neutral-500 transition-colors hover:bg-neutral-100 hover:text-neutral-800"
        >
          <LogOut className="h-4 w-4 shrink-0" strokeWidth={2} aria-hidden />
          Log out
        </button>
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
      <div className="flex min-h-screen items-center justify-center bg-[var(--bg)]">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-[var(--border)] border-t-neutral-700" />
          <div className="text-sm text-neutral-500" role="status">
            Loading…
          </div>
        </div>
      </div>
    );
  }

  const statusLabel =
    system?.status === "ok" ? "All systems operational" : "Systems degraded";

  return (
    <div className="flex min-h-screen bg-[var(--bg)] text-[var(--text)]">
      {/* Desktop sidebar */}
      <aside className="hidden w-[210px] shrink-0 flex-col border-r border-[var(--border)] bg-[var(--sidebar-bg)] lg:flex">
        <SidebarContent onNavigate={() => mobileOpen && setMobileOpen(false)} />
      </aside>

      {/* Mobile drawer */}
      {mobileOpen ? (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div
            className="absolute inset-0 bg-[var(--dark)]/40"
            onClick={() => setMobileOpen(false)}
            aria-hidden
          />
          <aside className="absolute inset-y-0 left-0 flex w-64 flex-col border-r border-[var(--border)] bg-[var(--sidebar-bg)] shadow-2xl">
            <div className="relative flex-1">
              <SidebarContent onNavigate={() => setMobileOpen(false)} />
            </div>
            <button
              onClick={() => setMobileOpen(false)}
              aria-label="Close navigation"
              className="absolute right-3 top-5 z-10 rounded-lg p-1.5 text-[var(--muted)] hover:bg-[var(--border)]"
            >
              <X className="h-5 w-5" />
            </button>
          </aside>
        </div>
      ) : null}

      <div className="flex min-w-0 flex-1 flex-col">
        {/* Top bar (reference .topbar) */}
        <header className="sticky top-0 z-30 flex h-[68px] items-center justify-between gap-4 border-b border-[var(--border)] bg-[var(--bg)] px-4 sm:px-7">
          <div className="flex items-center gap-3">
            <button
              className="rounded-lg p-2 text-[var(--muted)] hover:bg-[var(--border)] lg:hidden"
              onClick={() => setMobileOpen(true)}
              aria-label="Open navigation"
            >
              <Menu className="h-5 w-5" />
            </button>
            <div className="flex items-center gap-2 lg:hidden">
              <span className="text-sm font-bold text-[var(--text)]">VERIDEX</span>
            </div>
          </div>

          <div className="flex items-center gap-3 sm:gap-4">
            {/* Search (reference .search) */}
            <div className="hidden w-56 items-center gap-2 rounded-full border border-[var(--border)] bg-[var(--card)] px-4 py-2 text-sm text-[var(--muted)] sm:flex">
              <Search className="h-3.5 w-3.5" />
              <span className="text-[13px]">Search...</span>
            </div>

            {/* System status */}
            <div
              className={cn(
                "hidden items-center gap-2 rounded-full px-3 py-1.5 text-xs font-medium ring-1 ring-inset sm:inline-flex",
                system?.status === "ok"
                  ? "bg-neutral-100 text-neutral-700 ring-neutral-300"
                  : system
                    ? "bg-neutral-300 text-neutral-800 ring-neutral-400"
                    : "bg-neutral-100 text-neutral-500 ring-neutral-300",
              )}
              title={statusLabel}
            >
              <span
                className={cn(
                  "micro-pulse-dot h-1.5 w-1.5 rounded-full",
                  system?.status === "ok"
                    ? "bg-neutral-600"
                    : system
                      ? "bg-neutral-800"
                      : "bg-neutral-400",
                )}
                aria-hidden
              />
              {statusLabel}
            </div>

            {/* Notification indicator (reference .icon-btn) */}
            <button
              className="micro-press relative flex h-[34px] w-[34px] items-center justify-center rounded-full border border-[var(--border)] bg-[var(--card)] text-neutral-500 transition-colors hover:bg-neutral-100"
              aria-label="Notifications"
            >
              <Bell className="h-4 w-4" aria-hidden />
              <span className="absolute right-1.5 top-1.5 flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-black opacity-50" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-black" />
              </span>
            </button>

            {/* Officer identity */}
            <div className="flex items-center gap-3 border-l border-[var(--border)] pl-4">
              <div className="h-[34px] w-[34px] rounded-full bg-neutral-300" aria-hidden />
              <div className="hidden text-right sm:block">
                <div className="text-sm font-medium text-[var(--text)]">
                  {user.full_name || user.username}
                </div>
                <div className="text-xs capitalize text-[var(--muted)]">
                  {user.role}
                </div>
              </div>
              <button
                onClick={logout}
                className="rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 py-1.5 text-xs font-medium text-neutral-500 hover:bg-neutral-100 hover:text-neutral-800 transition-colors"
              >
                Sign out
              </button>
            </div>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto p-5 sm:p-7 xl:p-8">{children}</main>
      </div>
    </div>
  );
}
