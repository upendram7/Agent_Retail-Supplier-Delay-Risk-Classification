'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import {
  ApiList, DataTable, ErrorNotice, Panel, Shell, Status, TableCell, TimeFilter, api, traceUrl,
} from '../../components/observability';

type Trace = {
  trace_id: string; request_id: string; session_id: string; endpoint: string;
  environment: string; started_at: string; duration_ms: number; status: string;
};

export default function TracesPage() {
  const [timeRange, setTimeRange] = useState('24h');
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [page, setPage] = useState(1);
  const [data, setData] = useState<ApiList<Trace> | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    const range = new URLSearchParams({
      time_range: timeRange,
      page: String(page),
      per_page: '50',
      ...(timeRange === 'custom' && start ? { start } : {}),
      ...(timeRange === 'custom' && end ? { end } : {}),
    });
    api<ApiList<Trace>>(`/api/traces?${range.toString()}`)
      .then(setData).catch((reason: Error) => setError(reason.message));
  }, [timeRange, page, start, end]);

  return <Shell title="Distributed traces" description="Correlated request timelines across API handling, input guardrails, agents, tools, and retrieval.">
    <ErrorNotice message={error} />
    <Panel title="Trace explorer" action={<TimeFilter value={timeRange} onChange={(value) => { setTimeRange(value); setPage(1); }} start={start} end={end} onStartChange={setStart} onEndChange={setEnd} />}>
      <DataTable headers={['Trace ID', 'Started', 'Endpoint', 'Environment', 'Duration', 'Status']}>
        {(data?.items || []).map((trace) => <tr key={trace.trace_id} className="hover:bg-slate-50">
          <TableCell><Link href={traceUrl(trace.trace_id)} className="font-mono text-xs text-cyan-700 hover:underline">{trace.trace_id}</Link></TableCell>
          <TableCell className="whitespace-nowrap text-xs">{new Date(trace.started_at).toLocaleString()}</TableCell>
          <TableCell className="font-mono text-xs">{trace.endpoint}</TableCell>
          <TableCell>{trace.environment}</TableCell>
          <TableCell>{Number(trace.duration_ms || 0).toFixed(1)} ms</TableCell>
          <TableCell><Status value={trace.status} /></TableCell>
        </tr>)}
      </DataTable>
      {!data?.items.length && <p className="py-8 text-center text-sm text-slate-400">No traces in this time range.</p>}
      <div className="mt-4 flex items-center justify-between text-xs text-slate-500">
        <span>{data?.total ?? 0} traces · page {page}</span>
        <div className="flex gap-2"><button disabled={page <= 1} onClick={() => setPage(page - 1)} className="rounded-lg border px-3 py-2 disabled:opacity-40">Previous</button><button disabled={!data || page * data.per_page >= data.total} onClick={() => setPage(page + 1)} className="rounded-lg border px-3 py-2 disabled:opacity-40">Next</button></div>
      </div>
    </Panel>
  </Shell>;
}
