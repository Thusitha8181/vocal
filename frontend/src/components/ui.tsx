import type { ComponentProps, ReactNode } from "react";
import { cn } from "@/lib/utils";

export function Card({ className, ...props }: ComponentProps<"div">) {
  return (
    <div
      className={cn("rounded-xl border border-panel-border bg-panel", className)}
      {...props}
    />
  );
}

export function CardHeader({
  title,
  description,
  action,
}: {
  title: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-panel-border px-5 py-4">
      <div>
        <h2 className="text-sm font-semibold">{title}</h2>
        {description && <p className="mt-0.5 text-xs text-muted">{description}</p>}
      </div>
      {action}
    </div>
  );
}

const BADGE_TONES = {
  neutral: "bg-white/5 text-muted ring-white/10",
  accent: "bg-accent-soft text-violet-300 ring-violet-400/20",
  success: "bg-emerald-400/10 text-emerald-300 ring-emerald-400/20",
  warning: "bg-amber-400/10 text-amber-300 ring-amber-400/20",
  danger: "bg-red-400/10 text-red-300 ring-red-400/20",
} as const;

export type BadgeTone = keyof typeof BADGE_TONES;

export function Badge({
  tone = "neutral",
  className,
  ...props
}: ComponentProps<"span"> & { tone?: BadgeTone }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset",
        BADGE_TONES[tone],
        className,
      )}
      {...props}
    />
  );
}

export function Button({
  variant = "secondary",
  className,
  ...props
}: ComponentProps<"button"> & { variant?: "primary" | "secondary" | "danger" }) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-lg px-3.5 py-2 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50",
        variant === "primary" && "bg-accent text-white hover:bg-violet-500",
        variant === "secondary" &&
          "border border-panel-border bg-white/5 text-foreground hover:bg-white/10",
        variant === "danger" && "bg-red-500/90 text-white hover:bg-red-500",
        className,
      )}
      {...props}
    />
  );
}

export function Stat({ label, value, hint }: { label: string; value: ReactNode; hint?: string }) {
  return (
    <Card className="px-5 py-4">
      <p className="text-xs text-muted">{label}</p>
      <p className="mt-1 text-2xl font-semibold tracking-tight">{value}</p>
      {hint && <p className="mt-1 text-xs text-muted">{hint}</p>}
    </Card>
  );
}

export function PageHeader({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
        {description && <p className="mt-1 text-sm text-muted">{description}</p>}
      </div>
      {action}
    </div>
  );
}

export function EmptyState({ children }: { children: ReactNode }) {
  return <div className="px-5 py-12 text-center text-sm text-muted">{children}</div>;
}

export function ErrorNote({ error }: { error: string }) {
  return (
    <div className="rounded-lg border border-red-400/20 bg-red-400/5 px-4 py-3 text-sm text-red-300">
      {error}
    </div>
  );
}

export function ProgressBar({ value, max }: { value: number; max: number }) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0;
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/5">
      <div
        className={cn(
          "h-full rounded-full",
          pct > 90 ? "bg-danger" : pct > 70 ? "bg-warning" : "bg-accent",
        )}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}
