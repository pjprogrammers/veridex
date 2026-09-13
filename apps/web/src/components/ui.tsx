import { cn } from "@/lib/utils";

export function Card({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("card rounded-xl border border-[var(--border)] bg-[var(--card)]", className)}
      {...props}
    />
  );
}

export function CardHeader({
  title,
  subtitle,
  action,
}: {
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-[var(--border)] px-5 py-4">
      <div>
        <h2 className="text-[14.5px] font-bold text-[var(--text)]">{title}</h2>
        {subtitle ? (
          <p className="mt-0.5 text-xs text-[var(--muted)]">{subtitle}</p>
        ) : null}
      </div>
      {action}
    </div>
  );
}

export function Button({
  variant = "primary",
  size = "md",
  className,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "danger" | "ghost";
  size?: "sm" | "md";
}) {
  const variants = {
    primary:
      "bg-[var(--dark)] text-white hover:bg-[var(--dark-2)] disabled:opacity-50",
    secondary:
      "border border-[var(--border)] bg-[var(--card)] text-[var(--text)] hover:bg-neutral-100 disabled:text-[var(--muted)]",
    danger: "bg-black text-white hover:opacity-90 disabled:opacity-50",
    ghost: "text-neutral-500 hover:bg-neutral-100 hover:text-neutral-800 disabled:text-neutral-400",
  };
  const sizes = {
    sm: "h-8 px-3 text-xs",
    md: "h-10 px-4 text-sm",
  };
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-lg bg-gradient-to-br font-medium transition-all duration-150 active:scale-[0.98] disabled:cursor-not-allowed",
        variants[variant],
        sizes[size],
        className,
      )}
      {...props}
    />
  );
}

export function Badge({
  className,
  ...props
}: React.HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-semibold tracking-wide ring-1 ring-inset",
        className,
      )}
      {...props}
    />
  );
}

export function Input({
  className,
  ...props
}: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "h-10 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 text-sm text-[var(--text)] placeholder:text-neutral-400 focus:border-neutral-400 focus:outline-none focus:ring-2 focus:ring-neutral-300/40 transition-colors",
        className,
      )}
      {...props}
    />
  );
}

export function Select({
  className,
  ...props
}: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      className={cn(
        "h-10 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 text-sm text-[var(--text)] focus:border-neutral-400 focus:outline-none focus:ring-2 focus:ring-neutral-300/40 transition-colors",
        className,
      )}
      {...props}
    />
  );
}

export function Label({
  className,
  ...props
}: React.LabelHTMLAttributes<HTMLLabelElement>) {
  return (
    <label
      className={cn("mb-1 block text-xs font-medium text-[var(--muted)]", className)}
      {...props}
    />
  );
}

export function Spinner({ className }: { className?: string }) {
  return (
    <svg
      className={cn("h-4 w-4 animate-spin text-current", className)}
      viewBox="0 0 24 24"
      fill="none"
      aria-label="loading"
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
      />
    </svg>
  );
}

export function Alert({
  tone = "error",
  title,
  children,
}: {
  tone?: "error" | "info" | "success";
  title?: string;
  children?: React.ReactNode;
}) {
  const tones = {
    error: "border-neutral-300 bg-neutral-100 text-neutral-800",
    info: "border-neutral-300 bg-neutral-100 text-neutral-700",
    success: "border-neutral-300 bg-neutral-100 text-neutral-700",
  };
  const titles = {
    error: "text-black",
    info: "text-neutral-800",
    success: "text-neutral-800",
  };
  return (
    <div className={cn("rounded-lg border px-4 py-3 text-sm", tones[tone])}>
      {title ? <div className={cn("font-semibold", titles[tone])}>{title}</div> : null}
      {children ? <div className="mt-0.5 text-xs opacity-90 text-[var(--text)]">{children}</div> : null}
    </div>
  );
}

export function EmptyState({
  title,
  hint,
}: {
  title: string;
  hint?: string;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-[var(--border)] py-12 text-center">
      <div className="text-sm font-medium text-[var(--muted)]">{title}</div>
      {hint ? <div className="mt-1 text-xs text-[var(--muted)]/80">{hint}</div> : null}
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("micro-shimmer rounded-lg", className)} />;
}

export function Checkbox({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <label className="flex cursor-pointer items-center gap-2 text-sm text-[var(--text)]">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="h-4 w-4 rounded border-neutral-400 text-neutral-700 focus:ring-neutral-300/40"
      />
      {label}
    </label>
  );
}

export function Progress({
  value,
  className,
}: {
  value: number;
  className?: string;
}) {
  return (
    <div
      className={cn("progress-track h-2.5", className)}
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(value)}
    >
      <div
        className="progress-fill"
        style={{ width: `${Math.max(0, Math.min(100, value))}%` }}
      />
    </div>
  );
}

export function StatDisplay({
  label,
  value,
  suffix,
}: {
  label: string;
  value: React.ReactNode;
  suffix?: string;
}) {
  return (
    <div className="grid grid-cols-2 gap-x-4 gap-y-2 py-1 text-sm sm:grid-cols-1">
      <span className="text-[var(--muted)]">{label}</span>
      <span className="min-w-0 break-all text-right font-medium text-[var(--text)] sm:text-left">
        {value}
        {suffix ? <span className="ml-1 text-xs text-[var(--muted)]">{suffix}</span> : null}
      </span>
    </div>
  );
}
