"use client";

import { useEffect, useState } from "react";
import {
  Badge,
  type BadgeTone,
  Card,
  EmptyState,
  ErrorNote,
  PageHeader,
  ProgressBar,
} from "@/components/ui";
import { api, type Customer } from "@/lib/api";
import { formatData, formatDate, formatInr } from "@/lib/utils";

const STATUS_TONE: Record<Customer["account_status"], BadgeTone> = {
  active: "success",
  suspended: "danger",
  expired: "warning",
};

const BILL_TONE = { paid: "success", unpaid: "warning", overdue: "danger" } as const;

function scenario(c: Customer): string {
  if (c.account_status === "suspended") return "Services suspended for an overdue bill.";
  if (c.account_status === "expired") return "Prepaid validity expired; can only receive calls.";
  if (c.validity_ends_on) return "Prepaid validity ending soon, data nearly used up.";
  if (c.latest_bill?.line_items.some((i) => /roaming/i.test(i.description)))
    return "Bill is higher than the plan price because of a roaming pack.";
  if (c.latest_bill?.line_items.some((i) => /prorated/i.test(i.description)))
    return "Switched plans mid-cycle, so the bill is prorated.";
  if (c.autopay_enabled) return "Autopay customer, always paid on time.";
  return "";
}

function spokenPhone(phone: string): string {
  const digits = phone.replace(/\D/g, "").slice(-10);
  return `${digits.slice(0, 5)} ${digits.slice(5)}`;
}

export default function CustomersPage() {
  const [customers, setCustomers] = useState<Customer[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Customer[]>("/api/customers")
      .then(setCustomers)
      .catch(() => setError("Could not load customers. Is the backend running?"));
  }, []);

  return (
    <>
      <PageHeader
        title="Demo customers"
        description="Mock Lauki accounts in Postgres. To verify, tell Maya the registered number and the account holder's name."
      />
      {error && <ErrorNote error={error} />}
      {customers?.length === 0 && (
        <Card>
          <EmptyState>No customers. Run `make seed`.</EmptyState>
        </Card>
      )}
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {customers?.map((c) => {
          const dataTotal = (c.plan?.data_mb ?? 0) + (c.usage?.rollover_data_mb ?? 0);
          return (
            <Card key={c.id} className="flex flex-col p-5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-medium">{c.full_name}</p>
                  <p className="font-mono text-xs text-muted">{spokenPhone(c.phone)}</p>
                </div>
                <Badge tone={STATUS_TONE[c.account_status]}>{c.account_status}</Badge>
              </div>
              <p className="mt-3 text-sm">
                {c.plan?.name}{" "}
                <span className="text-muted">
                  · {c.plan?.connection_type} · {c.city}
                </span>
              </p>
              {scenario(c) && <p className="mt-1 text-xs text-violet-300">{scenario(c)}</p>}

              {c.usage && c.plan && (
                <div className="mt-4 space-y-2 text-xs">
                  <div className="flex justify-between text-muted">
                    <span>Data</span>
                    <span>
                      {formatData(c.usage.data_used_mb)} / {formatData(dataTotal)}
                    </span>
                  </div>
                  <ProgressBar value={c.usage.data_used_mb} max={dataTotal} />
                  <div className="flex justify-between text-muted">
                    <span>Voice</span>
                    <span>
                      {c.usage.voice_used_minutes} / {c.plan.voice_minutes} min
                    </span>
                  </div>
                  <ProgressBar value={c.usage.voice_used_minutes} max={c.plan.voice_minutes} />
                </div>
              )}

              <div className="mt-auto pt-4 text-xs">
                {c.latest_bill ? (
                  <div className="flex items-center justify-between rounded-lg bg-white/[0.03] px-3 py-2">
                    <span className="text-muted">
                      Bill due {formatDate(c.latest_bill.due_date)}
                    </span>
                    <span className="flex items-center gap-2">
                      {formatInr(c.latest_bill.amount_inr)}
                      <Badge tone={BILL_TONE[c.latest_bill.status]}>{c.latest_bill.status}</Badge>
                    </span>
                  </div>
                ) : (
                  c.validity_ends_on && (
                    <div className="rounded-lg bg-white/[0.03] px-3 py-2 text-muted">
                      Validity ends {formatDate(c.validity_ends_on)}
                    </div>
                  )
                )}
              </div>
            </Card>
          );
        })}
      </div>
    </>
  );
}
