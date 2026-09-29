"use client";

import { Mic, PhoneOff } from "lucide-react";
import { useEffect, useRef } from "react";
import { cn } from "@/lib/utils";

interface VoiceOrbProps {
  active: boolean;
  connecting: boolean;
  speaking: boolean;
  getInputVolume: () => number;
  getOutputVolume: () => number;
  onClick: () => void;
}

/** Mic button whose halo tracks the live input/output audio level. */
export function VoiceOrb({
  active,
  connecting,
  speaking,
  getInputVolume,
  getOutputVolume,
  onClick,
}: VoiceOrbProps) {
  const haloRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!active) return;
    let frame = 0;
    const tick = () => {
      const level = speaking ? getOutputVolume() : getInputVolume();
      if (haloRef.current) {
        haloRef.current.style.transform = `scale(${1 + Math.min(level, 1) * 0.6})`;
      }
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [active, speaking, getInputVolume, getOutputVolume]);

  return (
    <div className="relative grid size-44 place-items-center">
      {connecting && (
        <div className="animate-pulse-ring absolute inset-6 rounded-full bg-accent/40" />
      )}
      <div
        ref={haloRef}
        className={cn(
          "absolute inset-4 rounded-full transition-[background-color] duration-300",
          active ? (speaking ? "bg-accent/35" : "bg-emerald-400/25") : "bg-white/5",
        )}
      />
      <button
        onClick={onClick}
        disabled={connecting}
        aria-label={active ? "End conversation" : "Start conversation"}
        className={cn(
          "relative grid size-24 place-items-center rounded-full shadow-2xl transition",
          active ? "bg-red-500 hover:bg-red-400" : "bg-accent hover:bg-violet-500",
          connecting && "opacity-80",
        )}
      >
        {active ? <PhoneOff className="size-8 text-white" /> : <Mic className="size-8 text-white" />}
      </button>
    </div>
  );
}
