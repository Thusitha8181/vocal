"use client";

import { ChevronDown, FileText, Wrench } from "lucide-react";
import { useState } from "react";
import type { CallTurn } from "@/lib/api";
import { cn, formatTime, TOOL_LABELS } from "@/lib/utils";
import { Badge } from "./ui";

function ToolTurn({ turn }: { turn: CallTurn }) {
  const [open, setOpen] = useState(false);
  const args = turn.tool_args ? Object.entries(turn.tool_args) : [];
  return (
    <div className="ml-10 rounded-lg border border-dashed border-panel-border bg-white/[0.02] text-xs">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left"
      >
        <Wrench className="size-3.5 text-violet-300" />
        <span className="font-medium">{TOOL_LABELS[turn.tool_name ?? ""] ?? turn.tool_name}</span>
        {args.length > 0 && (
          <span className="truncate font-mono text-muted">
            {args.map(([k, v]) => `${k}: ${JSON.stringify(v)}`).join(", ")}
          </span>
        )}
        {turn.sources && <Badge tone="accent">{turn.sources.length} sources</Badge>}
        <ChevronDown className={cn("ml-auto size-3.5 text-muted transition", open && "rotate-180")} />
      </button>
      {open && (
        <div className="space-y-2 border-t border-panel-border px-3 py-3">
          {turn.sources ? (
            turn.sources.map((s, i) => (
              <div key={i} className="rounded-md bg-black/20 p-2.5">
                <div className="mb-1 flex items-center gap-2 text-muted">
                  <FileText className="size-3" />
                  <span>
                    {s.source} · page {s.page}
                  </span>
                  <span className="ml-auto font-mono">score {s.score.toFixed(3)}</span>
                </div>
                <p className="line-clamp-4 whitespace-pre-line text-foreground/80">
                  {s.content.split("\n\n").slice(1).join("\n\n") || s.content}
                </p>
              </div>
            ))
          ) : (
            <pre className="whitespace-pre-wrap font-mono text-[11px] text-foreground/80">
              {turn.content}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

export function TurnTimeline({ turns }: { turns: CallTurn[] }) {
  return (
    <div className="space-y-3">
      {turns.map((turn) =>
        turn.role === "tool" ? (
          <ToolTurn key={turn.id} turn={turn} />
        ) : (
          <div
            key={turn.id}
            className={cn("flex gap-3", turn.role === "user" && "flex-row-reverse text-right")}
          >
            <div
              className={cn(
                "grid size-7 shrink-0 place-items-center rounded-full text-[11px] font-semibold",
                turn.role === "user" ? "bg-white/10" : "bg-accent text-white",
              )}
            >
              {turn.role === "user" ? "C" : "M"}
            </div>
            <div className="max-w-[80%]">
              <div
                className={cn(
                  "inline-block rounded-2xl px-3.5 py-2 text-left text-sm leading-relaxed",
                  turn.role === "user"
                    ? "rounded-tr-sm bg-white/[0.07]"
                    : "rounded-tl-sm bg-accent-soft",
                )}
              >
                {turn.content}
              </div>
              <p className="mt-1 text-[11px] text-muted">
                {formatTime(turn.created_at)}
                {turn.latency_ms != null && ` · first token ${turn.latency_ms} ms`}
              </p>
            </div>
          </div>
        ),
      )}
    </div>
  );
}
