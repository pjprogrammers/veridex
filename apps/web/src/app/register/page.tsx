"use client";

import { useState } from "react";
import Link from "next/link";
import { useAuth, errorMessage } from "@/lib/auth";
import { Alert, Button, Input, Label, Spinner } from "@/components/ui";

export default function RegisterPage() {
  const { register } = useAuth();
  const [form, setForm] = useState({
    username: "",
    email: "",
    full_name: "",
    password: "",
    confirm: "",
  });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function set<K extends keyof typeof form>(key: K, value: string) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (form.password !== form.confirm) {
      setError("Passwords do not match");
      return;
    }
    if (form.password.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }
    setBusy(true);
    try {
      await register({
        username: form.username,
        email: form.email,
        password: form.password,
        ...(form.full_name ? { full_name: form.full_name } : {}),
      });
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
          <h1 className="text-xl font-semibold text-white">Create account</h1>
          <p className="mt-1 text-sm text-slate-400">Officer onboarding</p>
        </div>

        <form
          onSubmit={onSubmit}
          className="rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-xl"
        >
          {error ? <Alert title="Registration failed">{error}</Alert> : null}
          <div className={error ? "mt-4 space-y-4" : "space-y-4"}>
            <div>
              <Label className="text-slate-400">Username</Label>
              <Input
                value={form.username}
                onChange={(e) => set("username", e.target.value)}
                minLength={3}
                required
              />
            </div>
            <div>
              <Label className="text-slate-400">Email</Label>
              <Input
                type="email"
                value={form.email}
                onChange={(e) => set("email", e.target.value)}
                required
              />
            </div>
            <div>
              <Label className="text-slate-400">Full name (optional)</Label>
              <Input
                value={form.full_name}
                onChange={(e) => set("full_name", e.target.value)}
              />
            </div>
            <div>
              <Label className="text-slate-400">Password</Label>
              <Input
                type="password"
                value={form.password}
                onChange={(e) => set("password", e.target.value)}
                required
              />
            </div>
            <div>
              <Label className="text-slate-400">Confirm password</Label>
              <Input
                type="password"
                value={form.confirm}
                onChange={(e) => set("confirm", e.target.value)}
                required
              />
            </div>
          </div>
          <Button type="submit" disabled={busy} className="mt-6 w-full">
            {busy ? <Spinner /> : "Create account"}
          </Button>
        </form>

        <p className="mt-4 text-center text-xs text-slate-500">
          Already registered?{" "}
          <Link href="/login" className="font-medium text-indigo-400">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}