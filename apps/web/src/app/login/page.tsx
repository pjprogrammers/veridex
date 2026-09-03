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
    <div className="flex min-h-screen items-center justify-center bg-slate-950 px-4 py-12">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-indigo-600 text-lg font-bold text-white">
            V
          </div>
          <h1 className="text-xl font-semibold text-white">VERIDEX</h1>
          <p className="mt-1 text-sm text-slate-400">
            Identity &amp; Document Screening
          </p>
        </div>

        <form
          onSubmit={onSubmit}
          className="rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-xl"
        >
          {error ? <Alert title="Sign in failed">{error}</Alert> : null}
          <div className={error ? "mt-4" : ""}>
            <Label className="text-slate-400">Username</Label>
            <Input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              required
            />
          </div>
          <div className="mt-4">
            <Label className="text-slate-400">Password</Label>
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

        <p className="mt-4 text-center text-xs text-slate-500">
          New officer?{" "}
          <Link href="/register" className="font-medium text-indigo-400">
            Create an account
          </Link>
        </p>
        <div className="mt-6 rounded-lg border border-slate-800 bg-slate-900/60 p-3 text-xs text-slate-400">
          <p className="font-semibold text-slate-300">Synthetic demo logins</p>
          <p className="mt-1">
            Admin: <span className="font-mono">admin</span> /{" "}
            <span className="font-mono">Admin123!</span>
          </p>
          <p>
            Officer: <span className="font-mono">officer1</span> /{" "}
            <span className="font-mono">Officer123!</span>
          </p>
        </div>
      </div>
    </div>
  );
}