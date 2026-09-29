export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(
  /\/$/,
  "",
);

export type Role = "user" | "assistant" | "tool";

export interface Source {
  content: string;
  source: string;
  title: string;
  page: number;
  score: number;
}

export interface CallTurn {
  id: string;
  call_id: string;
  role: Role;
  content: string;
  tool_name: string | null;
  tool_args: Record<string, unknown> | null;
  sources: Source[] | null;
  latency_ms: number | null;
  created_at: string;
}

export interface Call {
  id: string;
  conversation_id: string;
  channel: "phone" | "web";
  status: "in_progress" | "completed" | "failed";
  caller_number: string | null;
  customer_id: string | null;
  customer_name: string | null;
  started_at: string;
  ended_at: string | null;
  duration_seconds: number | null;
  summary: string | null;
  successful: boolean | null;
  turn_count?: number;
}

export interface CallDetail extends Call {
  transcript: { role: string; message: string | null; time_in_call_secs: number | null }[] | null;
  call_metadata: Record<string, unknown> | null;
  turns: CallTurn[];
}

export interface Stats {
  total_calls: number;
  calls_last_24h: number;
  verified_rate: number;
  avg_duration_seconds: number | null;
  avg_first_token_ms: number | null;
  tool_usage: Record<string, number>;
}

export interface Plan {
  code: string;
  name: string;
  connection_type: "prepaid" | "postpaid";
  price_inr: number;
  validity_days: number;
  data_mb: number;
  voice_minutes: number;
  sms: number;
  benefits: string;
}

export interface Bill {
  id: string;
  period_start: string;
  period_end: string;
  due_date: string;
  amount_inr: number;
  status: "paid" | "unpaid" | "overdue";
  line_items: { description: string; amount_inr: number }[];
  paid_on: string | null;
}

export interface Usage {
  period_start: string;
  data_used_mb: number;
  voice_used_minutes: number;
  sms_used: number;
  rollover_data_mb: number;
}

export interface Customer {
  id: string;
  phone: string;
  full_name: string;
  email: string;
  city: string;
  plan_code: string;
  account_status: "active" | "suspended" | "expired";
  activated_on: string;
  bill_cycle_day: number | null;
  validity_ends_on: string | null;
  autopay_enabled: boolean;
  plan: Plan | null;
  latest_bill: Bill | null;
  usage: Usage | null;
}

export interface KnowledgeDocument {
  id: string;
  filename: string;
  title: string;
  pages: number;
  chunks: number;
  status: "pending" | "indexing" | "indexed" | "failed";
  error: string | null;
  indexed_at: string | null;
}

export type LiveEvent =
  | { type: "call.started" | "call.updated" | "call.ended"; call: Call }
  | { type: "call.turn"; call_id: string; turn: CallTurn };

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, { cache: "no-store", ...init });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      detail = (await response.json()).detail ?? detail;
    } catch {}
    throw new ApiError(response.status, detail);
  }
  return response.json() as Promise<T>;
}
