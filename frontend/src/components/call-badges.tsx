import { Globe, Phone } from "lucide-react";
import type { Call } from "@/lib/api";
import { Badge } from "./ui";

export function ChannelBadge({ channel }: { channel: Call["channel"] }) {
  return channel === "phone" ? (
    <Badge>
      <Phone className="size-3" /> Phone
    </Badge>
  ) : (
    <Badge>
      <Globe className="size-3" /> Web
    </Badge>
  );
}

export function StatusBadge({ call }: { call: Call }) {
  if (call.status === "in_progress") {
    return (
      <Badge tone="success">
        <span className="size-1.5 animate-pulse rounded-full bg-emerald-400" /> Live
      </Badge>
    );
  }
  if (call.status === "failed") return <Badge tone="danger">Failed</Badge>;
  if (call.successful === false) return <Badge tone="warning">Unresolved</Badge>;
  return <Badge tone="neutral">Completed</Badge>;
}
