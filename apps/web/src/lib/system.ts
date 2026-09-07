"use client";

import { useEffect, useState } from "react";
import type { HealthStatus } from "./types";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

/**
 * Polls the health endpoint and returns the current system status.
 * Returns null while the first check is in flight or the API is unreachable.
 */
export function useSystemStatus(intervalMs = 30000): HealthStatus | null {
  const [health, setHealth] = useState<HealthStatus | null>(null);

  useEffect(() => {
    let active = true;
    const controller = new AbortController();

    async function poll() {
      try {
        const res = await fetch(`${API_BASE}/health`, {
          signal: controller.signal,
          cache: "no-store",
        });
        if (res.ok) {
          const data = (await res.json()) as HealthStatus;
          if (active) setHealth(data);
        }
      } catch {
        // keep previous value; API may be temporarily unreachable
      }
    }

    poll();
    const id = window.setInterval(poll, intervalMs);
    return () => {
      active = false;
      controller.abort();
      window.clearInterval(id);
    };
  }, [intervalMs]);

  return health;
}
