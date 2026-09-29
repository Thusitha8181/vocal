"use client";

import { AudioLines, BookOpen, PhoneCall, Radio, Users } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/", label: "Talk to Maya", icon: AudioLines },
  { href: "/live", label: "Live monitor", icon: Radio },
  { href: "/calls", label: "Call history", icon: PhoneCall },
  { href: "/knowledge", label: "Knowledge base", icon: BookOpen },
  { href: "/customers", label: "Customers", icon: Users },
];

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="flex w-full shrink-0 flex-col border-b border-panel-border bg-panel/60 md:h-screen md:w-60 md:border-r md:border-b-0">
      <div className="flex items-center gap-2.5 px-5 py-5">
        <div className="grid size-8 place-items-center rounded-lg bg-accent">
          <AudioLines className="size-4 text-white" />
        </div>
        <div>
          <p className="text-sm font-semibold leading-none">Vocal</p>
          <p className="mt-1 text-[11px] text-muted">Lauki Phones support</p>
        </div>
      </div>
      <nav className="flex gap-1 overflow-x-auto px-3 pb-3 md:flex-col md:pb-0">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-2.5 whitespace-nowrap rounded-lg px-3 py-2 text-sm transition",
                active
                  ? "bg-accent-soft text-foreground"
                  : "text-muted hover:bg-white/5 hover:text-foreground",
              )}
            >
              <Icon className="size-4" />
              {label}
            </Link>
          );
        })}
      </nav>
      <div className="mt-auto hidden px-5 py-5 text-[11px] leading-relaxed text-muted md:block">
        ElevenLabs voice · LangGraph agent · Groq LLM · Qdrant RAG
      </div>
    </aside>
  );
}
