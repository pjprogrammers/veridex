"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  FileText,
  Maximize2,
} from "lucide-react";
import { api, errorFn } from "@/lib/api";
import { useCountUp } from "@/lib/use-count-up";
import type { CaseListResponse, RiskLevel, CaseRecord } from "@/lib/types";
import { RiskBadge } from "@/components/risk";
import { Alert, Badge, Card, Skeleton } from "@/components/ui";
import {
  cn,
  formatDate,
  STATUS_LABELS,
  STATUS_STYLES,
} from "@/lib/utils";
import { documentTypeLabel } from "@/lib/verify";

interface KPIDelta {
  value: number;
  text: string;
}

interface KPICardProps {
  label: string;
  value: number;
  delta?: KPIDelta;
  dark?: boolean;
  loading?: boolean;
}

function KPICard({ label, value, delta, dark, loading }: KPICardProps) {
  const shown = useCountUp(value);
  return (
    <div className={cn("kpi-card card-hover", dark ? "dark" : "light")}>
      <div className="kpi-label">{label}</div>
      {loading ? (
        <div className="py-1">
          <Skeleton className="h-7 w-20" />
        </div>
      ) : (
        <div className="kpi-value">{shown.toLocaleString()}</div>
      )}
      {!loading && delta ? (
        <div className={cn("kpi-delta", delta.value >= 0 ? "up" : "down")}>
          {Math.abs(delta.value)}% <span className="grey">{delta.text}</span>
        </div>
      ) : null}
    </div>
  );
}

function formatTick(v: number): string {
  if (v >= 1000 && v % 1000 === 0) return `${v / 1000}K`;
  if (v >= 1000) return `${(v / 1000).toFixed(1)}K`;
  return `${v}`;
}

const thCls =
  "px-2.5 pb-3 pt-0 text-left text-[11.5px] font-semibold text-[var(--muted)]";

export default function DashboardPage() {
  const [data, setData] = useState<CaseListResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<CaseListResponse>("/cases?limit=200")
      .then(setData)
      .catch((e) => setError(errorFn(e)));
  }, []);

  const stat = useMemo(() => {
    const cases = data?.cases ?? [];
    const byLevel: Record<RiskLevel, number> = {
      LOW: 0,
      MEDIUM: 0,
      HIGH: 0,
      CRITICAL: 0,
      UNKNOWN: 0,
    };
    for (const c of cases) byLevel[c.risk_level ?? "UNKNOWN"] += 1;
    const highRisk = cases.filter(
      (c) => c.risk_level === "HIGH" || c.risk_level === "CRITICAL",
    ).length;
    const manualReview = cases.filter(
      (c) =>
        c.status === "flagged" ||
        c.status === "under_examination" ||
        c.status === "in_review",
    ).length;
    const cleared = cases.filter(
      (c) => c.risk_level === "LOW" && c.status === "cleared",
    ).length;
    const criticalAlerts = cases.filter(
      (c) => c.risk_level === "CRITICAL",
    ).length;
    return { total: cases.length, byLevel, highRisk, manualReview, cleared, criticalAlerts };
  }, [data]);

  const recent = useMemo(() => {
    return [...(data?.cases ?? [])]
      .filter((c) => c.status !== "closed")
      .sort(
        (a, b) =>
          (b.updated_at ?? b.created_at ?? "").localeCompare(
            a.updated_at ?? a.created_at ?? "",
          ),
      )
      .slice(0, 8);
  }, [data]);

  // Monthly verification volume for the reference bar chart
  const months = useMemo(() => {
    const counts = new Map<string, number>();
    for (const c of data?.cases ?? []) {
      if (!c.created_at) continue;
      const d = new Date(c.created_at);
      const key = `${d.getFullYear()}-${d.getMonth()}`;
      counts.set(key, (counts.get(key) ?? 0) + 1);
    }
    const arr: { label: string; count: number }[] = [];
    const now = new Date();
    for (let i = 5; i >= 0; i--) {
      const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
      const key = `${d.getFullYear()}-${d.getMonth()}`;
      arr.push({
        label: d.toLocaleString("en-US", { month: "short" }),
        count: counts.get(key) ?? 0,
      });
    }
    return arr;
  }, [data]);

  const chart = useMemo(() => {
    const max = Math.max(1, ...months.map((m) => m.count));
    const step = Math.max(1, Math.ceil(max / 5));
    const top = step * 5;
    const ticks = [5, 4, 3, 2, 1, 0].map((i) => i * step).reverse();
    const tallest = months.reduce(
      (acc, m, i) => (m.count > months[acc].count ? i : acc),
      0,
    );
    return { top, ticks, tallest };
  }, [months]);

  // Calendar strip + growth (reference right panel)
  const days = useMemo(() => {
    const now = new Date();
    const arr: { label: string; num: number; active: boolean }[] = [];
    for (let i = 5; i >= 0; i--) {
      const d = new Date(now.getFullYear(), now.getMonth(), now.getDate() - i);
      arr.push({
        label: d.toLocaleString("en-US", { weekday: "short" }),
        num: d.getDate(),
        active: i === 0,
      });
    }
    return arr;
  }, []);

  const nowDate = new Date();
  const monthTitle = nowDate.toLocaleString("en-US", {
    month: "long",
    year: "numeric",
  });
  const clearedPct =
    stat.total > 0 ? Math.round((stat.cleared / stat.total) * 100) : 0;

  function documentSubject(c: CaseRecord): string | null {
    const meta = c.case_metadata as Record<string, unknown> | null;
    if (meta && typeof meta.subject === "string") return meta.subject;
    return c.description ?? null;
  }

  return (
    <div className="mx-auto max-w-[1200px] space-y-5 animate-fade-in-up">
      {/* Title (reference .topbar h1) */}
      <h1 className="text-xl font-bold text-[var(--text)]">Dashboard</h1>

      {error ? (
        <Alert title="Could not load dashboard">
          {error}. Confirm the API is running and you are signed in.
        </Alert>
      ) : null}

      {/* Filter row (reference .filter-row) */}
      <div className="flex items-center justify-end gap-2.5">
        <div className="segmented">
          <button type="button">Day</button>
          <button type="button">Week</button>
          <button type="button" className="active">Month</button>
          <button type="button">Year</button>
        </div>
        <div className="flex items-center gap-1.5 rounded-lg border border-[var(--border)] bg-[var(--card)] px-3.5 py-2 text-xs text-[var(--text)]">
          <span aria-hidden>📅</span>
          {nowDate.toLocaleDateString("en-US", {
            day: "numeric",
            month: "short",
            year: "numeric",
          })}
          {" - "}
          {new Date(
            nowDate.getFullYear(),
            nowDate.getMonth() + 1,
            0,
          ).toLocaleDateString("en-US", {
            day: "numeric",
            month: "short",
            year: "numeric",
          })}
        </div>
      </div>

      {/* KPI grid (reference .kpi-grid) */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KPICard
          label="Total Verifications"
          value={stat.total}
          delta={{ value: 12, text: "from last month" }}
          dark
          loading={!data}
        />
        <KPICard
          label="Cleared"
          value={stat.cleared}
          delta={{ value: 8, text: "from last month" }}
          loading={!data}
        />
        <KPICard
          label="Manual Review"
          value={stat.manualReview}
          delta={{ value: -3, text: "from last month" }}
          loading={!data}
        />
        <KPICard
          label="High Risk"
          value={stat.highRisk}
          delta={{ value: 5, text: "from last month" }}
          loading={!data}
        />
      </div>

      {/* Content row (reference .content-row) */}
      <div className="grid gap-4 lg:grid-cols-[1.6fr_1fr]">
        {/* Verification volume - reference .panel chart */}
        <Card className="p-[18px]">
          <div className="panel-head">
            <h3 className="text-[14.5px] font-bold text-[var(--text)]">
              Verification Volume
            </h3>
            <button
              type="button"
              className="flex h-[26px] w-[26px] items-center justify-center rounded-md border border-[var(--border)] text-[var(--muted)]"
              aria-label="Expand chart"
            >
              <Maximize2 className="h-3.5 w-3.5" aria-hidden />
            </button>
          </div>
          <div className="chart-wrap">
            <div className="y-axis" aria-hidden>
              {chart.ticks.map((t) => (
                <span key={t}>{formatTick(t)}</span>
              ))}
            </div>
            <div className="bars">
              {months.map((m, i) => (
                <div
                  key={`${m.label}-${i}`}
                  className={cn("bar-col", i === chart.tallest && "highlight")}
                >
                  <div
                    className="bar micro-grow-y"
                    style={{
                      height: `${(m.count / chart.top) * 100}%`,
                      animationDelay: `${i * 60}ms`,
                    }}
                  />
                  <div className="bar-month">{m.label}</div>
                </div>
              ))}
            </div>
          </div>
        </Card>

        {/* Calendar / clearance - reference calendar panel */}
        <Card className="p-[18px]">
          <div className="cal-head">
            <h3>{monthTitle}</h3>
            <div className="cal-nav" aria-hidden>
              <span className="cursor-pointer">‹</span>
              <span className="cursor-pointer">›</span>
            </div>
          </div>
          <div className="cal-strip">
            {days.map((d) => (
              <div
                key={`${d.label}-${d.num}`}
                className={cn("cal-day", d.active && "active")}
              >
                <span>{d.label}</span>
                <span className="num">{d.num}</span>
              </div>
            ))}
          </div>
          <div className="growth-box">
            <div>
              <div className="growth-label text-[var(--text)]">
                Clearance rate
              </div>
              <div className="growth-delta">
                {clearedPct}% of total verifications
              </div>
            </div>
            <div
              className="ring"
              style={{
                background: `conic-gradient(var(--dark) 0% ${clearedPct}%, #ececef ${clearedPct}% 100%)`,
              }}
              role="img"
              aria-label={`${clearedPct}% cleared`}
            >
              <span className="ring-inner text-[var(--text)]">
                {clearedPct}%
              </span>
            </div>
          </div>
        </Card>
      </div>

      {/* Recent verifications table (reference .table-panel) */}
      <Card className="p-[18px]">
        <div className="panel-head">
          <h3 className="text-[14.5px] font-bold text-[var(--text)]">
            Recent Verifications
          </h3>
        </div>
        {!data ? (
          <div className="space-y-3">
            <Skeleton className="h-11 w-full" />
            <Skeleton className="h-11 w-full" />
            <Skeleton className="h-11 w-full" />
          </div>
        ) : recent.length === 0 ? (
          <p className="py-6 text-sm text-[var(--muted)]">
            No verifications yet. Start one from the New Verification page.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-left text-[13px]">
              <thead>
                <tr>
                  <th className={thCls}>Case ID</th>
                  <th className={thCls}>Document</th>
                  <th className={thCls}>Subject</th>
                  <th className={thCls}>Risk</th>
                  <th className={thCls}>Status</th>
                  <th className={thCls}>Timestamp</th>
                </tr>
              </thead>
              <tbody>
                {recent.map((c) => {
                  const docType = (c.case_metadata as Record<string, unknown> | null)
                    ?.document_type as string | undefined;
                  return (
                    <tr key={c.id} className="border-b border-[var(--border)] last:border-0 transition-colors hover:bg-[#f6f7fb]">
                      <td className="py-3.5">
                        <Link
                          href={`/cases/${c.id}`}
                          className="font-mono text-xs font-semibold text-neutral-700 hover:text-black transition-colors"
                        >
                          {c.case_number}
                        </Link>
                      </td>
                      <td className="py-3.5">
                        <div className="flex items-center gap-2.5">
                          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-neutral-500 to-neutral-900">
                            <FileText className="h-4 w-4 text-white/70" aria-hidden />
                          </div>
                          <span className="text-[var(--text)]">
                            {documentTypeLabel(docType)}
                          </span>
                        </div>
                      </td>
                      <td className="max-w-[160px] truncate py-3.5 text-[var(--muted)]">
                        {documentSubject(c) ?? "—"}
                      </td>
                      <td className="py-3.5">
                        <RiskBadge level={c.risk_level} />
                      </td>
                      <td className="py-3.5">
                        <Badge className={STATUS_STYLES[c.status]}>
                          {STATUS_LABELS[c.status]}
                        </Badge>
                      </td>
                      <td className="py-3.5 text-xs text-[var(--muted)]">
                        {formatDate(c.updated_at ?? c.created_at)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Footer disclaimer */}
      <div className="flex items-center gap-2 rounded-xl border border-[var(--border)] bg-[var(--card)] px-5 py-3">
        <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-neutral-200">
          <AlertTriangle className="h-3.5 w-3.5 text-neutral-700" />
        </div>
        <p className="text-xs text-[var(--muted)]">
          <span className="font-semibold text-[var(--text)]">Screen priority:</span>{" "}
          LOW → MEDIUM → HIGH → CRITICAL. Manual review is required for any
          flagged or high-risk case before enforcement action.
        </p>
      </div>
    </div>
  );
}