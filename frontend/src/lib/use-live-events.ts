"use client";

import { useEffect, useEffectEvent, useState } from "react";
import { API_URL, type LiveEvent } from "./api";

const EVENT_TYPES = ["call.started", "call.updated", "call.ended", "call.turn"] as const;

/** Subscribes to the backend's server-sent event stream of live call activity. */
export function useLiveEvents(onEvent: (event: LiveEvent) => void): boolean {
  const [connected, setConnected] = useState(false);
  const handle = useEffectEvent(onEvent);

  useEffect(() => {
    const source = new EventSource(`${API_URL}/api/events`);
    const listener = (message: MessageEvent<string>) => handle(JSON.parse(message.data));
    source.onopen = () => setConnected(true);
    source.onerror = () => setConnected(false);
    EVENT_TYPES.forEach((type) => source.addEventListener(type, listener));
    return () => source.close();
  }, []);

  return connected;
}
