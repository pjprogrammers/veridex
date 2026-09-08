"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Activity,
  CheckCircle2,
  Database,
  MinusCircle,
  RefreshCw,
  Server,
  XCircle,
} from "lucide-react";
import {
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Tooltip as ReTooltip,
} from "recharts";
import type { HealthStatus } from "@/lib/types";
import { Card, CardHeader, Button, Skeleton, Alert } from "@/components/ui";
import { cn } from "@/lib/utils";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

const COLOR_OK = "#52525b";
const COLOR_ERROR = "#18181b";

function serviceIcon(name: string) {
  if (name === "postgres" || name === "redis" || name === "minio")
    return Database;
  return Server;
}

export default function SystemPage() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [ready, setReady] = useState<HealthStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const hRes = await fetch(`${API_BASE}/health`);
      const rRes = await fetch(`${API_BASE}/ready`);
      if (!hRes.ok || !rRes.ok)
        throw new Error(`Health endpoint returned ${hRes.status}`);
      setHealth((await hRes.json()) as HealthStatus);
      setReady((await rRes.json()) as HealthStatus);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to reach the API");
      setHealth(null);
      setReady(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const services = Object.entries(ready?.services ?? {});
  const okCount = services.filter(([, s]) => s === "ok").length;
  const errorCount = services.length - okCount;

  const pieData = [
    { name: "Operational", value: okCount },
    { name: "Unreachable", value: errorCount },
  ];

  const overall = ready?.status ?? health?.status ?? null;

  return (
    <div className="mx-auto max-w-5xl space-y-6 animate-fade-in-up">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-[var(--text)]">System Health</h1>
          <p className="mt-0.5 text-sm text-[var(--muted)]">
            Dependencies and service availability · API v{health?.version ?? "—"}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span
            className={cn(
              "inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold ring-1 ring-inset",
              !overall
                ? "bg-[#ececef] text-[var(--muted)] ring-[var(--border)]"
                : overall === "ok"
                  ? "bg-neutral-200/70 text-neutral-600 ring-neutral-400/40"
                  : overall === "degraded"
                    ? "bg-neutral-300/40 text-neutral-800 ring-neutral-400/40"
                    : "bg-neutral-200/80 text-black ring-neutral-400/40",
            )}
          >
            {overall ? (
              <>
                <Activity className="h-3.5 w-3.5" />
                {overall.toUpperCase()}
              </>
            ) : (
              "UNKNOWN"
            )}
          </span>
          <Button variant="secondary" size="sm" onClick={load} disabled={loading}>
            <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
            Refresh
          </Button>
        </div>
      </div>

      {error ? (
        <Alert title="Health check failed">
          {error} — the API may be offline or not yet started.
        </Alert>
      ) : null}

      {!ready && !error ? (
        <div className="grid gap-4 md:grid-cols-2">
          <Skeleton className="h-40 w-full" />
          <Skeleton className="h-40 w-full" />
        </div>
      ) : ready ? (
        <>
          <div className="grid gap-4 md:grid-cols-3">
            <Card className="card-hover p-5">
              <div className="flex items-start justify-between">
                <div>
                  <div className="text-xs font-semibold uppercase tracking-wider text-[var(--muted)]">
                    Services operational
                  </div>
                  <div className="mt-2 flex items-baseline gap-2">
                    <span className="text-3xl font-bold tracking-tight text-neutral-600">
                      {okCount}
                    </span>
                    <span className="text-sm text-[var(--muted)]">/ {services.length}</span>
                  </div>
                </div>
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-neutral-200/70 text-neutral-600">
                  <CheckCircle2 className="h-5 w-5" aria-hidden />
                </div>
              </div>
            </Card>
            <Card className="card-hover p-5">
              <div className="flex items-start justify-between">
                <div>
                  <div className="text-xs font-semibold uppercase tracking-wider text-[var(--muted)]">
                    Unreachable
                  </div>
                  <div className="mt-2 flex items-baseline gap-2">
                    <span
                      className={cn(
                        "text-3xl font-bold tracking-tight",
                        errorCount > 0 ? "text-black" : "text-neutral-600",
                      )}
                    >
                      {errorCount}
                    </span>
                    <span className="text-sm text-[var(--muted)]">/ {services.length}</span>
                  </div>
                </div>
                <div
                  className={cn(
                    "flex h-10 w-10 items-center justify-center rounded-xl",
                    errorCount > 0 ? "bg-neutral-200/80 text-black" : "bg-neutral-200/70 text-neutral-600",
                  )}
                >
                  <XCircle className="h-5 w-5" aria-hidden />
                </div>
              </div>
            </Card>
            <Card className="card-hover p-5">
              <div className="flex items-start justify-between">
                <div>
                  <div className="text-xs font-semibold uppercase tracking-wider text-[var(--muted)]">
                    Readiness
                  </div>
                  <div className="mt-2 text-3xl font-bold tracking-tight text-[var(--text)]">
                    {ready.status.toUpperCase()}
                  </div>
                </div>
                <div
                  className={cn(
                    "flex h-10 w-10 items-center justify-center rounded-xl",
                    ready.status === "ok"
                      ? "bg-neutral-200/70 text-neutral-600"
                      : "bg-neutral-300/40 text-neutral-800",
                  )}
                >
                  <Activity className="h-5 w-5" aria-hidden />
                </div>
              </div>
            </Card>
          </div>

          <Card>
            <CardHeader
              title="Dependency availability"
              subtitle="Realtime status of backing services"
            />
            <div className="grid gap-4 p-5 md:grid-cols-2">
              <div className="h-56">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={pieData}
                      dataKey="value"
                      nameKey="name"
                      innerRadius={50}
                      outerRadius={80}
                      paddingAngle={2}
                      strokeWidth={0}
                    >
                      <Cell fill={COLOR_OK} />
                      <Cell fill={COLOR_ERROR} />
                    </Pie>
                    <ReTooltip />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <ul className="space-y-3">
                {services.map(([name, status]) => {
                  const Icon = serviceIcon(name);
                  const ok = status === "ok";
                  return (
                    <li
                      key={name}
                      className="card-hover flex items-center justify-between rounded-lg border border-[var(--border)] bg-[var(--card)] px-4 py-3"
                    >
                      <div className="flex items-center gap-3">
                        <div
                          className={cn(
                            "flex h-8 w-8 items-center justify-center rounded-lg",
                            ok ? "bg-neutral-200/70 text-neutral-600" : "bg-neutral-200/80 text-black",
                          )}
                        >
                          <Icon className="h-4 w-4" />
                        </div>
                        <span className="text-sm font-medium capitalize text-[var(--text)]">
                          {name}
                        </span>
                      </div>
                      {ok ? (
                        <span className="inline-flex items-center gap-1.5 rounded-full bg-neutral-200/70 px-2.5 py-0.5 text-xs font-semibold text-neutral-600 ring-1 ring-inset ring-neutral-400/40">
                          <CheckCircle2 className="h-3.5 w-3.5" /> operational
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1.5 rounded-full bg-neutral-200/80 px-2.5 py-0.5 text-xs font-semibold text-black ring-1 ring-inset ring-neutral-400/40">
                          <XCircle className="h-3.5 w-3.5" /> unreachable
                        </span>
                      )}
                    </li>
                  );
                })}
                {services.length === 0 ? (
                  <li className="flex items-center gap-2 text-sm text-[var(--muted)]">
                    <MinusCircle className="h-4 w-4" /> No services reported
                  </li>
                ) : null}
              </ul>
            </div>
          </Card>

          <p className="text-xs text-[var(--muted)]">
            Last checked {new Date(ready.timestamp).toLocaleString()} · The
            readiness endpoint reports connectivity to PostgreSQL, Redis and
            MinIO; a degraded status does not necessarily block all features.
          </p>
        </>
      ) : null}
    </div>
  );
}
