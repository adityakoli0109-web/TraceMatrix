import { useCallback, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { Badge, Button, Card, Notice, StatusPill } from "../components/ui";
import { api } from "../lib/api";
import { GraphView } from "../components/GraphView";

function prettyDate(value: string | null | undefined) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

export function InvestigationPage() {
  const { id = "" } = useParams();
  const investigation = useQuery({ queryKey: ["investigation", id], queryFn: () => api.investigation(id), enabled: Boolean(id) });
  const graph = useQuery({ queryKey: ["investigation-graph", id], queryFn: () => api.graph(id), enabled: Boolean(id) });
  const transactions = useQuery({ queryKey: ["investigation-transactions", id], queryFn: () => api.transactions(id, "page=1&page_size=10"), enabled: Boolean(id) });
  const candidates = useQuery({ queryKey: ["investigation-candidates", id], queryFn: () => api.candidates(id), enabled: Boolean(id) });
  const evidence = useQuery({ queryKey: ["investigation-evidence", id], queryFn: () => api.evidence(id), enabled: Boolean(id) });
  const [selectedElement, setSelectedElement] = useState<Record<string, unknown> | null>(null);
  const handleSelect = useCallback((value: Record<string, unknown>) => setSelectedElement(value), []);

  if (investigation.isLoading) return <p className="text-sm text-muted">Loading investigation…</p>;
  if (investigation.isError || !investigation.data) {
    return <div className="space-y-3"><Notice>Could not load this investigation. It may not exist, or your session may have expired.</Notice><Link to="/"><Button variant="secondary">Back to dashboard</Button></Link></div>;
  }

  const item = investigation.data;
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link to="/" className="text-xs font-semibold text-[#2455d6] hover:underline">← All investigations</Link>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <h1 className="text-3xl font-semibold tracking-tight text-slate-900">{item.title}</h1>
            {item.is_fixture ? <Badge tone="warn">Demo data</Badge> : null}
          </div>
          <p className="mt-2 text-sm text-slate-500">Created {prettyDate(item.created_at)} <span className="mx-1.5">·</span> {item.seed_type}</p>
        </div>
        <StatusPill status={item.status} />
      </div>
      {item.is_fixture ? <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-950"><strong>Illustrative sample data.</strong> This fixture is for demonstrating the workflow only. It is not live blockchain evidence and does not identify a real person.</div> : null}
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {[
          ["Network nodes", graph.data?.nodes.length ?? "—", "Unique wallet addresses"],
          ["Transactions", transactions.data?.total ?? "—", "Observed in this case"],
          ["Evidence items", evidence.data?.items.length ?? "—", "Public-source records"],
          ["Review leads", candidates.data?.items.length ?? "—", "Require analyst verification"],
        ].map(([label, value, caption]) => (
          <Card key={label} className="rounded-2xl">
            <div className="text-xs font-medium text-slate-500">{label}</div>
            <div className="mt-2 text-3xl font-semibold tracking-tight text-slate-900">{value}</div>
            <div className="mt-1 text-[11px] text-slate-400">{caption}</div>
          </Card>
        ))}
      </div>
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.6fr)_minmax(280px,0.7fr)]">
        <Card title="Transaction network" className="rounded-2xl" action={<span className="text-[11px] text-slate-400">Select a node or connection for details</span>}>
          {graph.isLoading ? <p className="py-10 text-center text-sm text-slate-500">Building network graph…</p> : graph.isError ? <Notice>Graph data is currently unavailable.</Notice> : graph.data ? (
            <>
              {graph.data.nodes.length ? <GraphView data={graph.data} onSelect={handleSelect} highlight={[]} /> : <div className="grid h-64 place-items-center text-sm text-slate-500">No transaction connections are available for this case.</div>}
              <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-[11px] text-slate-500">
                <span className="inline-flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full bg-[#2455d6]" />Wallet</span>
                <span>Connection indicates graph relationship only; it does not prove common ownership.</span>
              </div>
              {selectedElement ? <div className="mt-3 rounded-xl border border-blue-100 bg-blue-50/70 p-3 text-xs text-slate-600"><span className="font-semibold text-slate-800">Selected {String(selectedElement.kind ?? "item")}:</span> <span className="mono break-all">{String(selectedElement.address ?? selectedElement.tx_hash ?? selectedElement.id ?? "Details unavailable")}</span></div> : null}
              {graph.data.truncated ? <p className="mt-2 text-xs text-slate-500">Graph output was truncated by the configured limits.</p> : null}
            </>
          ) : null}
        </Card>
        <div className="space-y-5">
        <Card title="Case parameters" className="rounded-2xl">
          <dl className="space-y-3 text-xs">
            <div><dt className="font-medium text-slate-500">Seed address / hash</dt><dd className="mono mt-1 break-all text-[11px] text-slate-800">{item.seed_value}</dd></div>
            <div><dt className="font-medium text-slate-500">Investigation objective</dt><dd className="mt-1 leading-5 text-slate-800">{item.objective || "Not specified"}</dd></div>
            <div className="grid grid-cols-2 gap-3 border-t border-slate-100 pt-3">
              <div><dt className="text-slate-500">Graph depth</dt><dd className="mt-1 font-semibold text-slate-800">{item.max_depth} hops</dd></div>
              <div><dt className="text-slate-500">Transaction limit</dt><dd className="mt-1 font-semibold text-slate-800">{item.max_transactions}</dd></div>
            </div>
          </dl>
        </Card>
        <Card title="Candidate leads" className="rounded-2xl">
          {candidates.isLoading ? <p className="text-xs text-slate-500">Loading analyst leads…</p> : candidates.isError ? <Notice>Candidate leads are currently unavailable.</Notice> : !candidates.data?.items.length ? <p className="text-xs leading-5 text-slate-500">No candidate leads are available. This is not evidence that no relationship exists.</p> : (
            <div className="space-y-3">
              {candidates.data.items.slice(0, 4).map((candidate) => (
                <div key={candidate.id} className="rounded-xl border border-slate-100 p-3">
                  <div className="flex items-center justify-between gap-2"><Badge tone="accent">{candidate.label.replaceAll("_", " ")}</Badge><span className="text-xs font-semibold tabular-nums text-slate-700">{Math.round(candidate.overall_score * 100)} pts</span></div>
                  <div className="mono mt-2 truncate text-[10px] text-slate-500">{candidate.wallet_address}</div>
                  <p className="mt-2 text-[11px] leading-5 text-slate-600">{candidate.explanation}</p>
                </div>
              ))}
              <p className="text-[10px] leading-4 text-slate-400">{candidates.data.disclaimer}</p>
            </div>
          )}
        </Card>
        </div>
      </div>
      <Card title="Recent transactions" className="rounded-2xl" action={<Badge>{transactions.data?.total ?? 0} total</Badge>}>
        {transactions.isLoading ? <p className="text-sm text-slate-500">Loading transactions…</p> : transactions.isError ? <Notice>Unable to load transactions for this case.</Notice> : !transactions.data?.items.length ? <p className="text-sm text-slate-500">No transactions have been stored for this investigation yet.</p> :
          <div className="overflow-x-auto"><table className="w-full min-w-[640px] text-left text-xs"><thead className="text-[10px] uppercase tracking-wide text-slate-400"><tr><th className="py-2 pr-3 font-semibold">Transaction</th><th className="pr-3 font-semibold">From</th><th className="pr-3 font-semibold">To</th><th className="pr-3 font-semibold">Block</th><th className="font-semibold">Source</th></tr></thead><tbody>{transactions.data.items.map((tx) => <tr key={tx.tx_hash} className="border-t border-slate-100"><td className="mono max-w-40 truncate py-3 pr-3 text-[10px] text-slate-700">{tx.tx_hash}</td><td className="mono max-w-32 truncate pr-3 text-[10px] text-slate-500">{tx.from_address}</td><td className="mono max-w-32 truncate pr-3 text-[10px] text-slate-500">{tx.to_address ?? "—"}</td><td className="pr-3 tabular-nums">{tx.block_number ?? "—"}</td><td>{tx.is_fixture ? <Badge tone="warn">Fixture</Badge> : <StatusPill status={tx.status ?? "stored"} />}</td></tr>)}</tbody></table></div>}
      </Card>
      <Notice>TraceMatrix supports investigative triage. A graph connection or score is not proof of identity or wrongdoing; verify evidence independently.</Notice>
    </div>
  );
}
