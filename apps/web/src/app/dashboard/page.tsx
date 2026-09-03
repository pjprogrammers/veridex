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
import { api } from "@/lib/api";
import type { CaseListResponse, RiskLevel } from "@/lib/types";
import { RiskBadge } from "@/components/risk";
import { Badge, Card, CardHeader, EmptyState, Skeleton } from "@/components/ui";
import {
  formatDate,
  STATUS_LABELS,
  STATUS_STYLES,
} from "@/lib/utils";

const RISK_BAR_COLORS: Record<RiskLevel, string> = {
  CRITICAL: "#dc2626",
  HIGH: "#fb923c",
  MEDIUM: "#f59e0b",
  LOW: "#10b981",
  UNKNOWN: "#94a3b8",
};

export default function OverviewPage() {
  const [data, setData] = useState<CaseListResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<CaseListResponse>("/cases?limit=50")
      .then(setData)
      .catch((e) => setError(e.message));
  }, []);

  const stats = useMemo(() => {
    const cases = data?.cases ?? [];
    const byLevel: Record<RiskLevel, number> = {
      LOW: 0,
      MEDIUM: 0,
      HIGH: 0,
      CRITICAL: 0,
      UNKNOWN: 0,
    };
    for (const c of cases) byLevel[c.risk_level ?? "UNKNOWN"] += 1;
    const flagged = cases.filter((c) => c.status === "flagged").length;
    const cleared = cases.filter((c) => c.status === "cleared").length;
    const highRisk = cases.filter(
      (c) => c.risk_level === "HIGH" || c.risk_level === "CRITICAL",
    ).length;
    const recent = [...cases]
      .sort((a, b) => (b.created_at ?? "").localeCompare(a.created_at ?? ""))
      .slice(0, 6);
    return { total: cases.length, flagged, cleared, highRisk, byLevel, recent };
  }, [data]);

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Overview</h1>
        <p className="mt-1 text-sm text-slate-500">
          Live screening console across all verification cases.
        </p>
      </div>

      {error ? (
        <Card>
          <div className="p-6 text-sm text-red-700">
            Could not reach the VERIDEX API: {error}
            <span className="mt-2 block text-xs text-slate-500">
              Ensure the FastAPI service is running on{" "}
              {process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1"}
              .
            </span>
          </div>
        </Card>
      ) : null}

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {[
          { label: "Total cases", value: data ? stats.total : null },
          { label: "Flagged", value: data ? stats.flagged : null },
          { label: "Cleared", value: data ? stats.cleared : null },
          { label: "High / critical risk", value: data ? stats.highRisk : null },
        ].map((s) => (
          <Card key={s.label} className="px-5 py-4">
            <div className="text-xs font-medium text-slate-500">{s.label}</div>
            {s.value === null ? (
              <Skeleton className="mt-2 h-8 w-12" />
            ) : (
              <div className="mt-1 text-3xl font-semibold text-slate-900">
                {s.value}
              </div>
            )}
          </Card>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-5">
        <Card className="lg:col-span-2">
          <CardHeader title="Risk distribution" />
          <div className="p-5">
            {stats.total === 0 ? (
              <p className="text-sm text-slate-500">No cases to chart yet.</p>
            ) : (
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={(
                      ["CRITICAL", "HIGH", "MEDIUM", "LOW", "UNKNOWN"] as RiskLevel[]
                    ).map((level) => ({
                      level,
                      count: stats.byLevel[level],
                      fill: RISK_BAR_COLORS[level],
                    }))}
                    layout="vertical"
                    margin={{ top: 0, right: 24, bottom: 0, left: 16 }}
                  >
                    <XAxis type="number" allowDecimals={false} hide />
                    <YAxis
                      type="category"
                      dataKey="level"
                      width={72}
                      tick={{ fontSize: 12, fill: "#475569" }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <Tooltip
                      cursor={{ fill: "rgba(100,116,139,0.08)" }}
                      formatter={(value) => [`${value} cases`, "Count"]}
                    />
                    <Bar
                      dataKey="count"
                      radius={[0, 6, 6, 0]}
                      barSize={22}
                      isAnimationActive={false}
                    >
                      {(
                        ["CRITICAL", "HIGH", "MEDIUM", "LOW", "UNKNOWN"] as RiskLevel[]
                      ).map((level) => (
                        <Cell
                          key={level}
                          fill={RISK_BAR_COLORS[level]}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        </Card>

        <Card className="lg:col-span-3">
          <CardHeader
            title="Recent cases"
            action={
              <Link
                href="/dashboard/cases"
                className="text-xs font-medium text-indigo-600 hover:text-indigo-500"
              >
                View all →
              </Link>
            }
          />
          {!data ? (
            <div className="space-y-3 p-5">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : stats.recent.length === 0 ? (
            <div className="p-5">
              <EmptyState
                title="No cases yet"
                hint="Create your first verification case from the Cases page."
              />
            </div>
          ) : (
            <ul className="divide-y divide-slate-100">
              {stats.recent.map((c) => (
                <li key={c.id}>
                  <Link
                    href={`/dashboard/cases/${c.id}`}
                    className="flex items-center justify-between gap-4 px-5 py-3 transition-colors hover:bg-slate-50"
                  >
                    <div className="min-w-0">
                      <div className="text-sm font-medium text-slate-900">
                        {c.case_number}
                      </div>
                      <div className="truncate text-xs text-slate-500">
                        {c.description || "No description"}
                      </div>
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      <Badge className={STATUS_STYLES[c.status]}>
                        {STATUS_LABELS[c.status]}
                      </Badge>
                      <RiskBadge level={c.risk_level} />
                      <span className="w-28 text-right text-xs text-slate-400">
                        {formatDate(c.created_at)}
                      </span>
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <p className="text-xs leading-5 text-slate-400">
        Ascending screen priority: LOW → MEDIUM → HIGH → CRITICAL. Flags
        indicate elevated risk indicators requiring manual officer review, not
        proof of fraud.
      </p>
    </div>
  );
}