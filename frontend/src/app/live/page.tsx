"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ChannelBadge, StatusBadge } from "@/components/call-badges";
import { TurnTimeline } from "@/components/turn-timeline";
import { Badge, Card, CardHeader, EmptyState, PageHeader } from "@/components/ui";
import { api, type Call, type CallDetail } from "@/lib/api";
import { useLiveEvents } from "@/lib/use-live-events";
import { formatRelative } from "@/lib/utils";

const RECENT_MS = 30 * 60 * 1000;

export default function LivePage() {
  const [calls, setCalls] = useState<Record<string, CallDetail>>({});

  useEffect(() => {
    (async () => {
      const recent = (await api<Call[]>("/api/calls?limit=20")).filter(
        (c) => c.status === "in_progress" && Date.now() - Date.parse(c.started_at) < RECENT_MS,
      );
      const details = await Promise.all(recent.map((c) => api<CallDetail>(`/api/calls/${c.id}`)));
      setCalls(Object.fromEntries(details.map((d) => [d.id, d])));
    })().catch(() => {});
  }, []);

  const connected = useLiveEvents((event) => {
    setCalls((prev) => {
      if (event.type === "call.turn") {
        const call = prev[event.call_id];
        return call ? { ...prev, [call.id]: { ...call, turns: [...call.turns, event.turn] } } : prev;
      }
      const existing: CallDetail | undefined = prev[event.call.id];
      return {
        ...prev,
        [event.call.id]: {
          ...event.call,
          transcript: existing?.transcript ?? null,
          call_metadata: existing?.call_metadata ?? null,
          turns: existing?.turns ?? [],
        },
      };
    });
  });

  const ordered = Object.values(calls).sort(
    (a, b) => Date.parse(b.started_at) - Date.parse(a.started_at),
  );

  return (
    <>
      <PageHeader
        title="Live monitor"
        description="Watch conversations as they happen: caller speech, agent replies and tool calls."
        action={
          <Badge tone={connected ? "success" : "danger"}>
            <span
              className={`size-1.5 rounded-full ${connected ? "animate-pulse bg-emerald-400" : "bg-red-400"}`}
            />
            {connected ? "Streaming" : "Disconnected"}
          </Badge>
        }
      />
      {ordered.length === 0 ? (
        <Card>
          <EmptyState>
            Waiting for calls. Dial the Twilio number or start a browser call from{" "}
            <Link href="/" className="text-violet-300 hover:underline">
              Talk to Maya
            </Link>
            .
          </EmptyState>
        </Card>
      ) : (
        <div className="grid gap-6 xl:grid-cols-2">
          {ordered.map((call) => (
            <Card key={call.id}>
              <CardHeader
                title={
                  <Link href={`/calls/${call.id}`} className="hover:text-violet-300">
                    {call.customer_name ?? call.caller_number ?? "Browser caller"}
                  </Link>
                }
                description={`Started ${formatRelative(call.started_at)}`}
                action={
                  <div className="flex gap-2">
                    <ChannelBadge channel={call.channel} />
                    <StatusBadge call={call} />
                  </div>
                }
              />
              <div className="max-h-[520px] overflow-y-auto px-5 py-5">
                {call.turns.length ? (
                  <TurnTimeline turns={call.turns} />
                ) : (
                  <EmptyState>Waiting for the first turn...</EmptyState>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}
    </>
  );
}
