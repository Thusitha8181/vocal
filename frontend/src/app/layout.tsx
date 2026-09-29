import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { Sidebar } from "@/components/sidebar";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Vocal - AI voice customer service",
  description:
    "Voice agent for Lauki Phones: ElevenLabs speech, LangGraph reasoning on Groq, and Qdrant RAG.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col font-sans md:flex-row">
        <Sidebar />
        <main className="min-w-0 flex-1 overflow-y-auto md:h-screen">
          <div className="mx-auto max-w-6xl px-5 py-8 md:px-8">{children}</div>
        </main>
      </body>
    </html>
  );
}
