"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth, errorMessage } from "@/lib/auth";
import { Alert, Button, Input, Label, Spinner } from "@/components/ui";

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await login(username, password);
      router.replace("/dashboard");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--bg)] px-4 py-12">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center">
            <div className="logo-badge" />
          </div>
          <h1 className="text-xl font-semibold text-[var(--text)]">VERIDEX</h1>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Identity &amp; Document Screening
          </p>
        </div>

        <form
          onSubmit={onSubmit}
          className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6 shadow-[0_8px_32px_rgba(28,29,33,0.06)]"
        >
          {error ? <Alert title="Sign in failed">{error}</Alert> : null}
          <div className={error ? "mt-4" : ""}>
            <Label>Username</Label>
            <Input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              required
            />
          </div>
          <div className="mt-4">
            <Label>Password</Label>
            <Input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
            />
          </div>
          <Button type="submit" disabled={busy} className="mt-6 w-full">
            {busy ? <Spinner /> : "Sign in"}
          </Button>
        </form>

        <p className="mt-4 text-center text-xs text-[var(--muted)]">
          New officer?{" "}
          <Link href="/register" className="font-medium text-neutral-500">
            Create an account
          </Link>
        </p>
        <div className="mt-6 rounded-lg border border-[var(--border)] bg-[var(--card)] p-3 text-xs text-[var(--muted)]">
          <p className="font-semibold text-[var(--text)]">Synthetic demo logins</p>
          <p className="mt-1">
            Admin: <span className="font-mono">admin</span> /{" "}
            <span className="font-mono">VeridexDev123!</span>
          </p>
          <p>
            Officer: <span className="font-mono">officer1</span> /{" "}
            <span className="font-mono">OfficerDev123!</span>
          </p>
          <p>
            Supervisor: <span className="font-mono">supervisor1</span> /{" "}
            <span className="font-mono">SupervisorDev123!</span>
          </p>
          <p>
            Auditor: <span className="font-mono">auditor1</span> /{" "}
            <span className="font-mono">AuditorDev123!</span>
          </p>
        </div>
      </div>
    </div>
  );
}
