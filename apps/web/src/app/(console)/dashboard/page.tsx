"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { AlertTriangle, CheckCircle2, ClipboardList, ShieldAlert } from "lucide-react";
import { api, errorFn } from "@/lib/api";
import type { CaseListResponse, RiskLevel, CaseRecord } from "@/lib/types";
import { RiskBadge } from "@/components/risk";
import {
  Alert,
  Badge,
  Card,
  CardHeader,
  EmptyState,
  Skeleton,
} from "@/components/ui";
import {
  cn,
  formatDate,
  RISK_BAR,
  STATUS_LABELS,
  STATUS_STYLES,
} from "@/lib/utils";
import { documentTypeLabel } from "@/lib/verify";

const RISK_ORDER_BAR: RiskLevel[] = ["LOW", "MEDIUM", "HIGH", "CRITICAL", "UNKNOWN"];
const RISK_BAR_COLORS: Record<RiskLevel, string> = {
  CRITICAL: "#dc2626",
  HIGH: "#fb923c",
  MEDIUM: "#f59e0b",
  LOW: "#10b981",
  UNKNOWN: "#94a3b8",
};

interface StatCard {
  label: string;
  value: number;
  icon: React.ReactNode;
  tone: string;
}

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
    const rare = cases.filter(
      (c) => c.risk_level === "LOW" && c.status === "cleared",
    ).length;
    const criticalAlerts = cases.filter(
      (c) => c.risk_level === "CRITICAL",
    ).length;
    return { total: cases.length, byLevel, highRisk, manualReview, rare, criticalAlerts };
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

  const cards: StatCard[] = [
    {
      label: "Total verifications",
      value: data ? stat.total : -1,
      icon: <ClipboardList className="h-4 w-4" />,
      tone: "bg-indigo-50 text-indigo-600",
    },
    {
      label: "Low risk",
      value: data ? stat.rare : -1,
      icon: <CheckCircle2 className="h-4 w-4" />,
      tone: "bg-emerald-50 text-emerald-600",
    },
    {
      label: "Manual review",
      value: data ? stat.manualReview : -1,
      icon: <ShieldAlert className="h-4 w-4" />,
      tone: "bg-amber-50 text-amber-600",
    },
    {
      label: "High risk",
      value: data ? stat.highRisk : -1,
      icon: <AlertTriangle className="h-4 w-4" />,
      tone: "bg-orange-50 text-orange-600",
    },
    {
      label: "Critical alerts",
      value: data ? stat.criticalAlerts : -1,
      icon: <AlertTriangle className="h-4 w-4" />,
      tone: "bg-red-50 text-red-600",
    },
  ];

  const chartData = RISK_ORDER_BAR.map((level) => ({
    level,
    count: stat.byLevel[level],
    fill: RISK_BAR_COLORS[level],
  }));

  function documentSubject(c: CaseRecord): string | null {
    const meta = c.case_metadata as Record<string, unknown> | null;
    if (meta && typeof meta.subject === "string") return meta.subject;
    return c.description ?? null;
  }

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Dashboard</h1>
        <p className="mt-1 text-sm text-slate-500">
          Live identity &amp; document verification across the checkpoint.
        </p>
      </div>

      {error ? (
        <Alert title="Could not load dashboard">
          {error}. Confirm the API is running and you are signed in.
        </Alert>
      ) : null}

      {/* Stat cards */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-5">
        {cards.map((c) => (
          <Card key={c.label} className="px-5 py-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-slate-500">{c.label}</span>
              <span className={cn("flex h-8 w-8 items-center justify-center rounded-lg", c.tone)} aria-hidden>
                {c.icon}
              </span>
            </div>
            {c.value === -1 ? (
              <Skeleton className="mt-3 h-9 w-12" />
            ) : (
              <div
                className="mt-2 text-3xl font-semibold text-slate-900"
                aria-label={`${c.label}: ${c.value}`}
              >
                {c.value}
              </div>
            )}
          </Card>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-5">
        {/* Risk visualization */}
        <Card className="lg:col-span-2">
          <CardHeader
            title="Risk distribution"
            subtitle="Verification cases by assessed risk level"
          />
          <div className="p-5">
            {!data ? (
              <Skeleton className="h-64 w-full" />
            ) : stat.total === 0 ? (
              <p className="text-sm text-slate-500">No cases to chart yet.</p>
            ) : (
              <div className="h-64" role="img" aria-label="Bar chart of case counts by risk level">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={chartData}
                    layout="vertical"
                    margin={{ top: 0, right: 24, bottom: 0, left: 16 }}
                    accessibilityLayer
                  >
                    <XAxis type="number" allowDecimals={false} hide />
                    <YAxis
                      type="category"
                      dataKey="level"
                      width={78}
                      tick={{ fontSize: 12, fill: "#475569" }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <Tooltip
                      cursor={{ fill: "rgba(100,116,139,0.08)" }}
                      formatter={(value) => [`${value} cases`, "Count"]}
                    />
                    <Bar dataKey="count" radius={[0, 6, 6, 0]} barSize={22} isAnimationActive={false}>
                      {chartData.map((d) => (
                        <Cell key={d.level} fill={d.fill} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
            <div className="mt-4 grid grid-cols-5 gap-1 text-center">
              {RISK_ORDER_BAR.map((level) => (
                <div key={level}>
                  <div className={cn("mx-auto h-1.5 w-6 rounded-full", RISK_BAR[level])} aria-hidden />
                  <div className="mt-1 text-[10px] text-slate-400">{level}</div>
                </div>
              ))}
            </div>
          </div>
        </Card>

        {/* Recent verifications */}
        <Card className="lg:col-span-3">
          <CardHeader
            title="Recent verifications"
            subtitle="Most recent activity across all cases"
            action={
              <Link
                href="/cases"
                className="text-xs font-medium text-indigo-600 hover:text-indigo-500"
              >
                View all →
              </Link>
            }
          />
          {!data ? (
            <div className="space-y-3 p-5">
              <Skeleton className="h-11 w-full" />
              <Skeleton className="h-11 w-full" />
              <Skeleton className="h-11 w-full" />
            </div>
          ) : recent.length === 0 ? (
            <div className="p-5">
              <EmptyState
                title="No verifications yet"
                hint="Start a new verification from the New Verification page."
              />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-slate-100 text-xs text-slate-500">
                    <th className="px-5 py-3 font-medium">Case ID</th>
                    <th className="px-5 py-3 font-medium">Document</th>
                    <th className="px-5 py-3 font-medium">Subject</th>
                    <th className="px-5 py-3 font-medium">Risk</th>
                    <th className="px-5 py-3 font-medium">Status</th>
                    <th className="px-5 py-3 font-medium">Timestamp</th>
                    <th className="px-5 py-3 font-medium">Officer</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-50">
                  {recent.map((c) => {
                    const docType = (c.case_metadata as Record<string, unknown> | null)
                      ?.document_type as string | undefined;
                    const officer = (c.case_metadata as Record<string, unknown> | null)
                      ?.officer as string | undefined;
                    return (
                      <tr key={c.id} className="hover:bg-slate-50">
                        <td className="px-5 py-3">
                          <Link
                            href={`/cases/${c.id}`}
                            className="font-mono text-xs font-medium text-indigo-600 hover:text-indigo-500"
                          >
                            {c.case_number}
                          </Link>
                        </td>
                        <td className="px-5 py-3 text-xs text-slate-600">
                          {documentTypeLabel(docType)}
                        </td>
                        <td className="max-w-[160px] truncate px-5 py-3 text-xs text-slate-600">
                          {documentSubject(c) ?? "—"}
                        </td>
                        <td className="px-5 py-3">
                          <RiskBadge level={c.risk_level} />
                        </td>
                        <td className="px-5 py-3">
                          <Badge className={STATUS_STYLES[c.status]}>
                            {STATUS_LABELS[c.status]}
                          </Badge>
                        </td>
                        <td className="px-5 py-3 text-xs text-slate-400">
                          {formatDate(c.updated_at ?? c.created_at)}
                        </td>
                        <td className="px-5 py-3 text-xs text-slate-500">
                          {officer ?? "—"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>

      <p className="text-xs leading-5 text-slate-400">
        Screen priority: LOW → MEDIUM → HIGH → CRITICAL. Manual review is
        required for any flagged or high-risk case before enforcement action.
      </p>
    </div>
  );
}
