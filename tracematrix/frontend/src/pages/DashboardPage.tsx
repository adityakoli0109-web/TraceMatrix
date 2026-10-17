import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Badge, Button, Card, EmptyState, StatusPill } from "../components/ui";
import { api } from "../lib/api";

export function DashboardPage() {
  const dash = useQuery({ queryKey: ["dashboard"], queryFn: api.dashboard });
  const list = useQuery({
    queryKey: ["investigations"],
    queryFn: () => api.investigations("page=1&page_size=20&sort=created_at&order=desc"),
  });

  if (dash.isLoading) return <p className="text-sm text-muted">Loading dashboard…</p>;
  if (dash.isError) return <p className="text-sm text-danger">Unable to load dashboard.</p>;
  const data = dash.data!;

  if (data.empty) {
    return (
      <div className="space-y-6">
        <div className="rounded-3xl bg-[#101b2d] px-7 py-9 text-white shadow-xl shadow-slate-900/10 sm:px-10 sm:py-12">
          <div className="text-xs font-semibold uppercase tracking-[0.18em] text-sky-300">Analyst workspace</div>
          <h1 className="mt-3 max-w-2xl text-3xl font-semibold tracking-tight sm:text-4xl">Turn transaction trails into reviewable leads.</h1>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-300">Start with a wallet address or transaction hash. TraceMatrix organizes graph connections and public evidence so analysts can review them in context.</p>
          <Link to="/investigations/new" className="mt-6 inline-flex">
            <Button className="rounded-xl bg-sky-400 px-5 py-3 font-semibold text-slate-950 hover:bg-sky-300">Start an investigation <span aria-hidden="true" className="ml-2">→</span></Button>
          </Link>
        </div>
        <EmptyState
          title="Your case workspace is ready"
          body="No investigations have been created yet. Create your first case to review its scope before any processing begins."
          action={<Link to="/investigations/new"><Button variant="secondary" className="rounded-xl px-4 py-2">Create first case</Button></Link>}
        />
      </div>
    );
  }

  const tiles = [
    ["Investigations", data.totals.investigations, "All tracked cases"],
    ["Active", data.totals.active, "Currently in progress"],
    ["Completed", data.totals.completed, "Ready for review"],
    ["Wallets mapped", data.totals.wallets, "Across investigations"],
    ["Transactions", data.totals.transactions, "Available to analyze"],
  ] as const;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="text-xs font-semibold uppercase tracking-[0.16em] text-[#2455d6]">Overview</div>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-900">Investigation dashboard</h1>
          <p className="mt-1 text-sm text-slate-500">A clear view of cases, processing, and review activity.</p>
        </div>
        <Link to="/investigations/new">
          <Button className="rounded-xl px-4 py-2.5 shadow-sm">＋ New investigation</Button>
        </Link>
      </div>
      {data.recent.some((item) => item.is_fixture) ? (
        <div className="flex items-start gap-3 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-950">
          <span aria-hidden="true" className="mt-0.5">ⓘ</span>
          <p><strong>Demo data is active.</strong> Fixture investigations are illustrative sample data, not live blockchain findings.</p>
        </div>
      ) : null}
      <div className="grid grid-cols-2 gap-3 xl:grid-cols-5">
        {tiles.map(([label, value, caption], index) => (
          <Card key={label} className="rounded-2xl border-slate-200/80 shadow-sm">
            <div className="flex items-start justify-between">
              <div>
                <div className="text-xs font-medium text-slate-500">{label}</div>
                <div className="mt-3 text-3xl font-semibold tracking-tight text-slate-900">{value}</div>
              </div>
              <div className={`grid h-9 w-9 place-items-center rounded-xl text-sm font-bold ${index === 1 ? "bg-emerald-50 text-emerald-700" : index === 2 ? "bg-violet-50 text-violet-700" : "bg-blue-50 text-blue-700"}`}>
                {["↗", "◷", "✓", "◎", "⇄"][index]}
              </div>
            </div>
            <div className="mt-2 text-[11px] text-slate-400">{caption}</div>
          </Card>
        ))}
      </div>
      <div className="grid gap-5 xl:grid-cols-[0.82fr_1.18fr]">
        <Card title="Processing activity" className="rounded-2xl border-slate-200/80 shadow-sm" action={<span className="text-[11px] font-medium text-slate-400">Latest jobs</span>}>
          {data.jobs.length === 0 ? (
            <p className="py-5 text-sm text-slate-500">No background jobs recorded yet.</p>
          ) : (
            <table className="w-full text-left text-xs">
              <thead className="text-[11px] uppercase tracking-wide text-slate-400">
                <tr className="text-muted">
                  <th className="py-2 font-semibold">Job</th>
                  <th className="font-semibold">Status</th>
                  <th className="text-right font-semibold">Progress</th>
                </tr>
              </thead>
              <tbody>
                {data.jobs.map((job) => (
                  <tr key={job.id} className="border-t border-slate-100">
                    <td className="py-3 pr-2 font-medium text-slate-700">{job.job_type.replaceAll("_", " ")}</td>
                    <td className="py-3">
                      <StatusPill status={job.status} />
                    </td>
                    <td className="py-3 text-right tabular-nums text-slate-500">{job.progress}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
        <Card title="Recent investigations" className="rounded-2xl border-slate-200/80 shadow-sm" action={<Link to="/investigations/new" className="text-xs font-semibold text-[#2455d6] hover:underline">View workflow →</Link>}>
          <div className="overflow-x-auto">
          <table className="w-full min-w-[520px] text-left text-xs">
            <thead className="text-[11px] uppercase tracking-wide text-slate-400">
              <tr className="text-muted">
                <th className="py-2 font-semibold">Case</th>
                <th className="font-semibold">Status</th>
                <th className="font-semibold">Seed address</th>
              </tr>
            </thead>
            <tbody>
              {(list.data?.items ?? data.recent).map((inv) => (
                <tr key={inv.id} className="border-t border-slate-100">
                  <td className="py-3 pr-3">
                    <Link className="font-semibold text-slate-800 hover:text-[#2455d6]" to={`/investigations/${inv.id}`}>{inv.title}</Link>
                    {inv.is_fixture ? (
                      <span className="ml-2"><Badge tone="warn">DEMO DATA</Badge></span>
                    ) : null}
                  </td>
                  <td className="py-3 pr-3">
                    <StatusPill status={inv.status} />
                  </td>
                  <td className="mono max-w-[180px] truncate py-3 text-[11px] text-slate-500">{inv.seed_value}</td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        </Card>
      </div>
    </div>
  );
}
