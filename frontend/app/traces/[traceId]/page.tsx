'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import {
  DataTable, ErrorNotice, Panel, Shell, Status, TableCell, api, formatNumber, traceUrl,
} from '../../../components/observability';

type Span = {
  span_id: string; parent_span_id?: string; span_name: string; span_type: string;
  agent_name?: string; tool_name?: string; started_at: string; duration_ms: number;
  status: string; input_json?: string; output_json?: string; error?: string;
  metadata_json?: string;
};
type TraceDetail = {
  trace: { trace_id: string; request_id: string; session_id: string; endpoint: string; started_at: string; duration_ms: number; status: string; environment: string };
  spans: Span[]; logs: Record<string, unknown>[]; llm_calls: Record<string, unknown>[];
  agent_runs: Record<string, unknown>[]; tool_calls: Record<string, unknown>[];
  retrievals: Record<string, unknown>[]; errors: Record<string, unknown>[];
  guardrails: Record<string, unknown>[];
};

export default function TraceDetailPage() {
  const params = useParams<{ traceId: string }>();
  const traceId = decodeURIComponent(params.traceId);
  const [data, setData] = useState<TraceDetail | null>(null);
  const [selected, setSelected] = useState<Span | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    api<TraceDetail>(`/api/traces/${encodeURIComponent(traceId)}`)
      .then(setData).catch((reason: Error) => setError(reason.message));
  }, [traceId]);

  const startedAt = data ? new Date(data.trace.started_at).getTime() : 0;
  const maxDuration = Math.max(Number(data?.trace.duration_ms || 0), 1);

  return <Shell title="Trace detail" description="Request-correlated view of spans, logs, model calls, agents, tools, retrievals, guardrail decisions, and errors.">
    <ErrorNotice message={error} />
    {data && <>
      <div className="mb-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Summary label="Trace ID" value={data.trace.trace_id} />
        <Summary label="Request ID" value={data.trace.request_id} />
        <Summary label="Endpoint" value={data.trace.endpoint} />
        <Summary label="Duration / status" value={`${formatNumber(data.trace.duration_ms, 1)} ms · ${data.trace.status}`} />
      </div>
      <Panel title="Trace waterfall" action={<Status value={data.trace.status} />}>
        <div className="space-y-2">
          {[...data.spans].sort((a, b) => a.started_at.localeCompare(b.started_at)).map((span) => {
            const offset = Math.max(0, new Date(span.started_at).getTime() - startedAt);
            const left = Math.min((offset / maxDuration) * 100, 96);
            const width = Math.max(Math.min((Number(span.duration_ms || 0) / maxDuration) * 100, 100 - left), 1.5);
            return <button key={span.span_id} onClick={() => setSelected(span)} className="grid w-full grid-cols-[150px_1fr_75px] items-center gap-3 rounded-lg px-2 py-2 text-left hover:bg-slate-50">
              <span className="truncate text-xs font-medium text-slate-700">{span.span_name}</span>
              <span className="relative h-6 rounded bg-slate-50"><span className={`absolute top-1 h-4 rounded ${span.status === 'ERROR' ? 'bg-rose-500' : span.span_type === 'api' ? 'bg-blue-500' : span.span_type === 'tool' ? 'bg-amber-500' : 'bg-cyan-500'}`} style={{ left: `${left}%`, width: `${width}%` }} /></span>
              <span className="text-right text-[10px] text-slate-500">{formatNumber(span.duration_ms, 1)} ms</span>
            </button>;
          })}
          {!data.spans.length && <p className="py-5 text-center text-sm text-slate-400">This request has no recorded spans.</p>}
        </div>
        <div className="mt-3 flex flex-wrap gap-4 border-t pt-3 text-[10px] text-slate-500"><Legend color="bg-blue-500" label="API" /><Legend color="bg-cyan-500" label="Agent / guardrail / retrieval" /><Legend color="bg-amber-500" label="Tool" /><Legend color="bg-rose-500" label="Error" /></div>
      </Panel>

      <div className="mt-5 grid gap-5 xl:grid-cols-2">
        <RecordPanel title={`Logs · ${data.logs.length}`} records={data.logs} />
        <RecordPanel title={`LLM calls · ${data.llm_calls.length}`} records={data.llm_calls} />
        <RecordPanel title={`Agent runs · ${data.agent_runs.length}`} records={data.agent_runs} />
        <RecordPanel title={`Tool calls · ${data.tool_calls.length}`} records={data.tool_calls} />
        <RecordPanel title={`RAG retrievals · ${data.retrievals.length}`} records={data.retrievals} />
        <RecordPanel title={`Guardrails · ${data.guardrails.length}`} records={data.guardrails} />
        <Panel title={`Errors · ${data.errors.length}`}>
          {data.errors.length ? <RecordPanelContent records={data.errors} /> : <p className="text-sm text-slate-400">No errors in this trace.</p>}
        </Panel>
      </div>
    </>}
    {selected && <div className="fixed inset-0 z-20 grid place-items-center bg-slate-950/40 p-4" onClick={() => setSelected(null)}>
      <section className="max-h-[85vh] w-full max-w-3xl overflow-auto rounded-2xl bg-white p-5 shadow-xl" onClick={(event) => event.stopPropagation()}>
        <div className="mb-3 flex items-center justify-between"><h2 className="font-semibold">{selected.span_name}</h2><button onClick={() => setSelected(null)} className="rounded-lg px-3 py-1 text-sm hover:bg-slate-100">Close</button></div>
        <p className="mb-3 text-xs text-slate-500">{selected.span_type} · {formatNumber(selected.duration_ms, 1)} ms · {selected.status}</p>
        <pre className="overflow-auto rounded-xl bg-slate-950 p-4 text-xs leading-5 text-emerald-100">{JSON.stringify(selected, null, 2)}</pre>
      </section>
    </div>}
    <Link href="/traces" className="mt-5 inline-block text-sm font-semibold text-cyan-700">← All traces</Link>
  </Shell>;
}

function Summary({ label, value }: { label: string; value: string }) {
  return <div className="rounded-xl border border-slate-200 bg-white p-4"><p className="text-[10px] font-bold uppercase text-slate-400">{label}</p><p className="mt-2 break-all font-mono text-xs font-semibold text-slate-800">{value}</p></div>;
}

function Legend({ color, label }: { color: string; label: string }) {
  return <span className="flex items-center gap-1.5"><i className={`h-2.5 w-2.5 rounded ${color}`} />{label}</span>;
}

function RecordPanel({ title, records }: { title: string; records: Record<string, unknown>[] }) {
  return <Panel title={title}>{records.length ? <RecordPanelContent records={records} /> : <p className="text-sm text-slate-400">No correlated events.</p>}</Panel>;
}

function RecordPanelContent({ records }: { records: Record<string, unknown>[] }) {
  return <div className="max-h-64 space-y-2 overflow-auto">{records.map((record, index) => <details key={String(record.id || record.span_id || index)} className="rounded-lg border border-slate-100 p-3">
    <summary className="cursor-pointer text-xs font-medium text-slate-700">{String(record.message || record.agent_name || record.tool_name || record.guardrail_name || record.model_name || record.event_type || record.span_name || record.status || 'Event')}</summary>
    <pre className="mt-2 overflow-auto rounded bg-slate-950 p-3 text-[10px] text-emerald-100">{JSON.stringify(record, null, 2)}</pre>
  </details>)}</div>;
}
