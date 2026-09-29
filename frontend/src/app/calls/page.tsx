"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ChannelBadge, StatusBadge } from "@/components/call-badges";
import { Card, EmptyState, ErrorNote, PageHeader, Stat } from "@/components/ui";
import { api, type Call, type Stats } from "@/lib/api";
import { useLiveEvents } from "@/lib/use-live-events";
import { formatDuration, formatRelative, TOOL_LABELS } from "@/lib/utils";

export default function CallsPage() {
  const [calls, setCalls] = useState<Call[] | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [c, s] = await Promise.all([api<Call[]>("/api/calls"), api<Stats>("/api/stats")]);
      setCalls(c);
      setStats(s);
    } catch {
      setError("Could not load calls. Is the backend running?");
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- initial data fetch
    load();
  }, [load]);

  useLiveEvents((event) => {
    if (event.type !== "call.turn") load();
  });

  const tools = stats ? Object.entries(stats.tool_usage).sort((a, b) => b[1] - a[1]) : [];

  return (
    <>
      <PageHeader title="Call history" description="Every conversation handled by the agent." />
      {error && <ErrorNote error={error} />}

      {stats && (
        <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
          <Stat label="Total calls" value={stats.total_calls} hint={`${stats.calls_last_24h} in the last 24h`} />
          <Stat
            label="Callers verified"
            value={`${Math.round(stats.verified_rate * 100)}%`}
            hint="Identified by caller ID or voice verification"
          />
          <Stat label="Avg. call length" value={formatDuration(stats.avg_duration_seconds)} />
          <Stat
            label="Avg. time to first word"
            value={stats.avg_first_token_ms ? `${stats.avg_first_token_ms} ms` : "-"}
            hint="From request to first streamed token"
          />
        </div>
      )}

      {tools.length > 0 && (
        <div className="mb-6 flex flex-wrap gap-2 text-xs text-muted">
          <span>Tool usage:</span>
          {tools.map(([name, count]) => (
            <span key={name} className="rounded-full bg-white/5 px-2.5 py-0.5">
              {TOOL_LABELS[name] ?? name} · {count}
            </span>
          ))}
        </div>
      )}

      <Card className="overflow-hidden">
        {calls && calls.length === 0 ? (
          <EmptyState>No calls yet. Start one from the Talk to Maya page.</EmptyState>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-panel-border text-left text-xs text-muted">
                <tr>
                  <th className="px-5 py-3 font-medium">Caller</th>
                  <th className="px-5 py-3 font-medium">Channel</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium">Summary</th>
                  <th className="px-5 py-3 font-medium">Duration</th>
                  <th className="px-5 py-3 font-medium">Started</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-panel-border">
                {calls?.map((call) => (
                  <tr key={call.id} className="transition hover:bg-white/[0.02]">
                    <td className="px-5 py-3">
                      <Link href={`/calls/${call.id}`} className="font-medium hover:text-violet-300">
                        {call.customer_name ?? "Unverified caller"}
                      </Link>
                      <p className="text-xs text-muted">{call.caller_number ?? "Browser"}</p>
                    </td>
                    <td className="px-5 py-3">
                      <ChannelBadge channel={call.channel} />
                    </td>
                    <td className="px-5 py-3">
                      <StatusBadge call={call} />
                    </td>
                    <td className="max-w-sm px-5 py-3 text-xs text-muted">
                      <p className="line-clamp-2">
                        {call.summary ?? `${call.turn_count ?? 0} turns logged`}
                      </p>
                    </td>
                    <td className="px-5 py-3 text-muted">{formatDuration(call.duration_seconds)}</td>
                    <td className="whitespace-nowrap px-5 py-3 text-muted">
                      {formatRelative(call.started_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  );
}
