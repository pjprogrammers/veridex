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
const ORIGIN = API_BASE.replace(/\/api\/v1\/?$/, "");

const COLOR_OK = "#10b981";
const COLOR_ERROR = "#ef4444";

function serviceIcon(name: string) {
  if (name === "postgres" || name === "redis" || name === "minio")
    return Database;
  return Server;
}

export default function SystemHealthPage() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${ORIGIN}/health`);
      if (!res.ok) throw new Error(`Health endpoint returned ${res.status}`);
      setHealth((await res.json()) as HealthStatus);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to reach the API");
      setHealth(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const services = Object.entries(health?.services ?? {});
  const okCount = services.filter(([, s]) => s === "ok").length;
  const errorCount = services.length - okCount;

  const pieData = [
    { name: "Operational", value: okCount },
    { name: "Unreachable", value: errorCount },
  ];

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">System Health</h1>
          <p className="mt-0.5 text-sm text-slate-500">
            Dependencies and service availability · API v{health?.version ?? "—"}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span
            className={cn(
              "inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold ring-1 ring-inset",
              !health
                ? "bg-slate-100 text-slate-600 ring-slate-500/20"
                : health.status === "ok"
                  ? "bg-emerald-50 text-emerald-700 ring-emerald-600/20"
                  : health.status === "degraded"
                    ? "bg-amber-50 text-amber-700 ring-amber-600/20"
                    : "bg-red-50 text-red-700 ring-red-600/20",
            )}
          >
            {health ? (
              <>
                <Activity className="h-3.5 w-3.5" />
                {health.status.toUpperCase()}
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

      {!health && !error ? (
        <div className="grid gap-4 md:grid-cols-2">
          <Skeleton className="h-40 w-full" />
          <Skeleton className="h-40 w-full" />
        </div>
      ) : health ? (
        <>
          <div className="grid gap-4 md:grid-cols-3">
            <Card className="p-5">
              <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Services operational
              </div>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="text-3xl font-bold text-emerald-600">
                  {okCount}
                </span>
                <span className="text-sm text-slate-500">/ {services.length}</span>
              </div>
            </Card>
            <Card className="p-5">
              <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Unreachable
              </div>
              <div className="mt-2 flex items-baseline gap-2">
                <span
                  className={cn(
                    "text-3xl font-bold",
                    errorCount > 0 ? "text-red-600" : "text-emerald-600",
                  )}
                >
                  {errorCount}
                </span>
                <span className="text-sm text-slate-500">/ {services.length}</span>
              </div>
            </Card>
            <Card className="p-5">
              <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Overall status
              </div>
              <div className="mt-2 text-2xl font-bold text-slate-800">
                {health.status.toUpperCase()}
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
                      className="flex items-center justify-between rounded-lg border border-slate-100 px-4 py-3"
                    >
                      <div className="flex items-center gap-3">
                        <Icon className="h-4 w-4 text-slate-400" />
                        <span className="text-sm font-medium capitalize text-slate-800">
                          {name}
                        </span>
                      </div>
                      {ok ? (
                        <span className="inline-flex items-center gap-1.5 text-sm font-medium text-emerald-600">
                          <CheckCircle2 className="h-4 w-4" /> ok
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1.5 text-sm font-medium text-red-600">
                          <XCircle className="h-4 w-4" /> error
                        </span>
                      )}
                    </li>
                  );
                })}
                {services.length === 0 ? (
                  <li className="flex items-center gap-2 text-sm text-slate-500">
                    <MinusCircle className="h-4 w-4" /> No services reported
                  </li>
                ) : null}
              </ul>
            </div>
          </Card>

          <p className="text-xs text-slate-400">
            Last checked {new Date(health.timestamp).toLocaleString()} · The
            health endpoint reports connectivity to PostgreSQL, Redis and
            MinIO; a degraded status does not necessarily block all features.
          </p>
        </>
      ) : null}
    </div>
  );
}
