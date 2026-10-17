import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useNavigate } from "react-router-dom";
import { z } from "zod";
import { Button, Card, Field, Input, Notice } from "../components/ui";
import { api } from "../lib/api";

const seedRe = /^(0x[0-9a-fA-F]{40}|0x[0-9a-fA-F]{64})$/;
const schema = z.object({
  title: z.string().min(3),
  description: z.string(),
  seed_value: z.string().regex(seedRe, "Must be a 0x address (40 hex) or transaction hash (64 hex)"),
  objective: z.string(),
  max_depth: z.coerce.number().min(1).max(5),
  max_transactions: z.coerce.number().min(1).max(500),
  date_from: z.string().optional(),
  date_to: z.string().optional(),
});

export function InvestigationNewPage() {
  const navigate = useNavigate();
  const [scope, setScope] = useState<Record<string, unknown> | null>(null);
  const [pending, setPending] = useState<z.infer<typeof schema> | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const form = useForm({
    resolver: zodResolver(schema),
    defaultValues: {
      title: "",
      description: "",
      seed_value: "",
      objective: "",
      max_depth: 2,
      max_transactions: 100,
      date_from: "",
      date_to: "",
    },
  });

  async function submit(values: z.infer<typeof schema>, confirm: boolean) {
    setSubmitError(null);
    const body = {
      ...values,
      date_from: values.date_from ? new Date(values.date_from).toISOString() : null,
      date_to: values.date_to ? new Date(values.date_to).toISOString() : null,
      confirm_scope: confirm,
      selected_sources: { github: true, threat_feeds: true, chain: true },
    };
    const result = await api.createInvestigation(body);
    if ("confirmation_required" in result && result.confirmation_required) {
      setScope(result.scope);
      setPending(values);
      return;
    }
    if ("investigation" in result) navigate(`/investigations/${result.investigation.id}`);
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <Link to="/" className="text-xs font-semibold text-[#2455d6] hover:underline">← Dashboard</Link>
        <div className="mt-3 text-xs font-semibold uppercase tracking-[0.16em] text-[#2455d6]">New case · Step 1 of 2</div>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-900">Define investigation scope</h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">Set a clear objective and bounded transaction window. You’ll review the scope before processing starts.</p>
      </div>
      <Notice>
        <strong className="text-slate-700">Data note:</strong> Address history requires a configured Etherscan-compatible provider. Missing credentials are reported as unavailable; TraceMatrix does not invent live results.
      </Notice>
      <Card title="Investigation details" className="rounded-2xl">
        <form
          className="grid gap-3"
          onSubmit={form.handleSubmit(async (values) => {
            try {
              await submit(values, false);
            } catch (err) {
              setSubmitError(err instanceof Error ? err.message : "Could not review investigation scope.");
            }
          })}
        >
          <Field label="Case title" error={form.formState.errors.title?.message}>
            <Input {...form.register("title")} />
          </Field>
          <Field label="Description">
            <Input {...form.register("description")} />
          </Field>
          <Field label="Starting point · wallet address or transaction hash" error={form.formState.errors.seed_value?.message}>
            <Input className="mono" placeholder="0x followed by 40 or 64 hexadecimal characters" {...form.register("seed_value")} />
          </Field>
          <Field label="Objective">
            <Input {...form.register("objective")} />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Graph depth · 1–5 hops">
              <Input type="number" {...form.register("max_depth")} />
            </Field>
            <Field label="Transaction limit · 1–500">
              <Input type="number" {...form.register("max_transactions")} />
            </Field>
            <Field label="From date">
              <Input type="date" {...form.register("date_from")} />
            </Field>
            <Field label="To date">
              <Input type="date" {...form.register("date_to")} />
            </Field>
          </div>
          {submitError ? <p role="alert" className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{submitError}</p> : null}
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-4">
            <span className="text-xs text-slate-400">No processing starts until you confirm.</span>
            <Button className="rounded-xl px-5 py-2.5" type="submit" disabled={form.formState.isSubmitting}>
              {form.formState.isSubmitting ? "Reviewing…" : "Review scope →"}
            </Button>
          </div>
        </form>
      </Card>
      {scope && pending ? (
        <Card title="Review before processing" className="rounded-2xl border-blue-200 shadow-md shadow-blue-950/5">
          <p className="mb-4 text-sm leading-6 text-slate-500">Confirm that this case is authorized, appropriately scoped, and ready to process.</p>
          <div className="grid gap-3 sm:grid-cols-2">
            {Object.entries(scope).map(([key, value]) => (
              <div key={key} className="rounded-xl bg-slate-50 p-3">
                <div className="text-[10px] font-bold uppercase tracking-[0.12em] text-slate-400">{key.replaceAll("_", " ")}</div>
                <div className="mt-1 break-words text-xs leading-5 text-slate-800">{String(value)}</div>
              </div>
            ))}
          </div>
          {submitError ? <p role="alert" className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{submitError}</p> : null}
          <div className="mt-5 flex flex-wrap justify-end gap-2">
            <Button variant="secondary" onClick={() => { setScope(null); setPending(null); }}>Edit scope</Button>
            <Button className="rounded-xl px-5" disabled={form.formState.isSubmitting} onClick={async () => {
              try {
                await submit(pending, true);
              } catch (err) {
                setSubmitError(err instanceof Error ? err.message : "Could not start investigation.");
              }
            }}>
              {form.formState.isSubmitting ? "Starting…" : "Confirm and start"}
            </Button>
          </div>
        </Card>
      ) : null}
    </div>
  );
}
