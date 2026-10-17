import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Badge, Button, Card, Field, Input, Notice, Select, StatusPill } from "../components/ui";
import { api, type Source } from "../lib/api";

export function SourcesPage() {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [sourceType, setSourceType] = useState("threat_feed");
  const [endpoint, setEndpoint] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const sources = useQuery({ queryKey: ["osint-sources"], queryFn: api.sources });
  const integrations = useQuery({ queryKey: ["integrations"], queryFn: api.integrations });
  const create = useMutation({
    mutationFn: () => api.createSource({ name: name.trim(), source_type: sourceType, endpoint: endpoint.trim(), enabled: true, config: {} }),
    onSuccess: async () => {
      setName(""); setEndpoint(""); setMessage("Source saved successfully."); setError(null);
      await queryClient.invalidateQueries({ queryKey: ["osint-sources"] });
    },
    onError: (err) => { setError(err instanceof Error ? err.message : "Could not save source."); setMessage(null); },
  });

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <div><h1 className="text-base font-semibold">OSINT sources</h1><p className="mt-1 text-[13px] text-muted">Manage public-data sources used by the investigation workflow. Only add sources you are authorized to access.</p></div>
      {message ? <Notice>{message}</Notice> : null}
      {error ? <p className="text-sm text-danger">{error}</p> : null}
      <Card title="Add a source">
        <form className="grid gap-3 md:grid-cols-2" onSubmit={(event) => { event.preventDefault(); setError(null); setMessage(null); create.mutate(); }}>
          <Field label="Source name"><Input value={name} onChange={(event) => setName(event.target.value)} required minLength={2} placeholder="Example public threat feed" /></Field>
          <Field label="Source type"><Select value={sourceType} onChange={(event) => setSourceType(event.target.value)}><option value="threat_feed">Threat feed</option><option value="github">GitHub / public repository</option><option value="blockchain">Blockchain data provider</option><option value="other">Other public source</option></Select></Field>
          <div className="md:col-span-2"><Field label="Endpoint URL"><Input type="url" value={endpoint} onChange={(event) => setEndpoint(event.target.value)} required placeholder="https://example.org/feed.json" /></Field></div>
          <div className="md:col-span-2"><Button type="submit" disabled={create.isPending || !name.trim() || !endpoint.trim()}>{create.isPending ? "Saving…" : "Save source"}</Button></div>
        </form>
        {sourceType === "threat_feed" ? <p className="mt-2 text-xs text-muted">Threat-feed endpoints are validated by the backend. Use trusted HTTPS feeds only.</p> : null}
      </Card>
      <Card title="Configured sources" action={<Badge>{sources.data?.items.length ?? 0} sources</Badge>}>
        {sources.isLoading ? <p className="text-[13px] text-muted">Loading sources…</p> : sources.isError ? <Notice>Could not load configured sources. Check your login and backend connection.</Notice> : !sources.data?.items.length ? <p className="text-[13px] text-muted">No sources configured yet. Add one above to get started.</p> :
          <div className="overflow-x-auto"><table className="w-full text-left text-[12px]"><thead><tr className="text-muted"><th className="py-2 pr-3 font-medium">Name</th><th className="pr-3 font-medium">Type</th><th className="pr-3 font-medium">Endpoint</th><th className="pr-3 font-medium">Status</th><th className="font-medium">Last success</th></tr></thead><tbody>{sources.data.items.map((source: Source) => <tr key={source.id} className="border-t border-line"><td className="py-2 pr-3 font-medium">{source.name}</td><td className="pr-3">{source.source_type}</td><td className="max-w-56 truncate pr-3" title={source.endpoint}>{source.endpoint}</td><td className="pr-3"><StatusPill status={source.status} />{!source.enabled ? <span className="ml-1"><Badge>Disabled</Badge></span> : null}{source.last_error ? <p className="mt-1 max-w-48 text-danger">{source.last_error}</p> : null}</td><td>{source.last_success_at ? new Date(source.last_success_at).toLocaleString() : "—"}</td></tr>)}</tbody></table></div>}
      </Card>
      <Card title="Integration status">
        {integrations.isLoading ? <p className="text-[13px] text-muted">Checking integrations…</p> : integrations.isError ? <Notice>Integration status unavailable.</Notice> : !integrations.data ? <Notice>Integration status unavailable.</Notice> : <div className="grid gap-2 md:grid-cols-2">
          <div className="border border-line p-3"><div className="text-xs text-muted">Ethereum RPC</div><div className="mt-1"><StatusPill status={integrations.data.ethereum.rpc} /></div><p className="mt-1 text-xs text-muted">{integrations.data.ethereum.limitations.join(" ")}</p></div>
          <div className="border border-line p-3"><div className="text-xs text-muted">GitHub</div><div className="mt-1"><StatusPill status={integrations.data.github.configured ? "configured" : "not_configured"} /></div><p className="mt-1 text-xs text-muted">{integrations.data.github.rate_limit_note}</p></div>
          <div className="border border-line p-3"><div className="text-xs text-muted">Threat feeds</div><div className="mt-1"><StatusPill status={integrations.data.threat_feeds.status} /></div><p className="mt-1 text-xs text-muted">Allowed hosts: {integrations.data.threat_feeds.allowlist.join(", ") || "none configured"}</p></div>
          <div className="border border-line p-3"><div className="text-xs text-muted">Background jobs</div><div className="mt-1"><StatusPill status={integrations.data.jobs.mode} /></div></div>
        </div>}
      </Card>
    </div>
  );
}
