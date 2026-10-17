import { useState } from "react";
import { Button, Card, Field, Input, Notice, StatusPill } from "../components/ui";
import { api, type LookupResponse } from "../lib/api";

export function ExplorerPage() {
  const [q, setQ] = useState("");
  const [result, setResult] = useState<LookupResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  return (
    <div className="space-y-3">
      <h1 className="text-base font-semibold">Blockchain explorer</h1>
      <form
        className="flex gap-2"
        onSubmit={async (e) => {
          e.preventDefault();
          setError(null);
          try {
            setResult(await api.lookup(q.trim()));
          } catch (err) {
            setError(err instanceof Error ? err.message : "Lookup failed");
          }
        }}
      >
        <Field label="Address or transaction hash">
          <Input className="mono w-[420px]" value={q} onChange={(e) => setQ(e.target.value)} />
        </Field>
        <Button className="mt-5" type="submit">
          Lookup
        </Button>
      </form>
      {error ? <p className="text-sm text-danger">{error}</p> : null}
      {result?.status === "not_configured" ? (
        <Notice>
          Ethereum RPC is not configured. Set ETH_RPC_URL. {result.error} Historical address lists also need
          ETHERSCAN_API_KEY.
        </Notice>
      ) : null}
      {result?.status === "error" ? <Notice>{result.error}</Notice> : null}
      {result?.status === "ok" && result.result ? (
        <Card title="Result">
          {Boolean(result.result.is_fixture) && (
            <Notice>Fixture result — not live blockchain data.</Notice>
          )}
          {result.result.limitation ? <Notice>{String(result.result.limitation)}</Notice> : null}
          <pre className="mt-2 max-h-[480px] overflow-auto bg-paper p-2 text-[11px]">
            {JSON.stringify(result.result, null, 2)}
          </pre>
          <div className="mt-2">
            <StatusPill status={String(result.result.provider ?? "ok")} />
          </div>
        </Card>
      ) : null}
    </div>
  );
}
