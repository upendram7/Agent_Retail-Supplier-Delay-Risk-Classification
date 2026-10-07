'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import {
  ApiList, DataTable, ErrorNotice, Panel, Shell, Status, TableCell,
  TimeFilter, api, queryString, traceUrl,
} from '../../components/observability';

type LogItem = {
  id: number; timestamp: string; level: string; service: string; environment: string;
  request_id?: string; trace_id?: string; session_id?: string; agent_name?: string;
  tool_name?: string; model_name?: string; endpoint?: string; message: string;
  latency_ms?: number; status?: string; error_type?: string;
};

export default function LogsPage() {
  const [filters, setFilters] = useState({
    time_range: '24h', start: '', end: '', environment: '', level: '', service: '',
    agent: '', tool: '', model: '', status: '', request_id: '', trace_id: '',
    session_id: '', endpoint: '', q: '', sort: 'timestamp', order: 'desc',
  });
  const [page, setPage] = useState(1);
  const [data, setData] = useState<ApiList<LogItem> | null>(null);
  const [selected, setSelected] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState('');
  const [refresh, setRefresh] = useState(false);

  const loadLogs = useCallback(() => {
    const query = queryString({
      ...filters, start: filters.time_range === 'custom' ? filters.start : undefined,
      end: filters.time_range === 'custom' ? filters.end : undefined, page, per_page: 50,
    });
    api<ApiList<LogItem>>(`/api/logs?${query}`)
      .then((result) => { setData(result); setError(''); })
      .catch((reason: Error) => setError(reason.message));
  }, [filters, page]);

  useEffect(() => { loadLogs(); }, [loadLogs]);
  useEffect(() => {
    if (!refresh) return;
    const interval = window.setInterval(loadLogs, 15000);
    return () => window.clearInterval(interval);
  }, [refresh, loadLogs]);

  async function showDetails(id: number) {
    try { setSelected(await api<Record<string, unknown>>(`/api/logs/${id}`)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Unable to load log details'); }
  }

  function exportJson() {
    if (!data) return;
    download('application-logs.json', JSON.stringify(data.items, null, 2), 'application/json');
  }

  function exportCsv() {
    if (!data) return;
    const headers = ['timestamp', 'level', 'service', 'environment', 'request_id', 'trace_id', 'session_id', 'agent_name', 'tool_name', 'model_name', 'endpoint', 'message', 'latency_ms', 'status', 'error_type'];
    const csv = [headers.join(','), ...data.items.map((item) => headers.map((header) => csvEscape(String(item[header as keyof LogItem] ?? ''))).join(','))].join('\n');
    download('application-logs.csv', csv, 'text/csv');
  }

  return (
    <Shell title="Log explorer" description="Search and inspect structured application logs. Select a trace identifier to open its correlated request timeline.">
      <ErrorNotice message={error} />
      <Panel title="Filters" action={<div className="flex gap-2"><button onClick={exportCsv} className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold">Export CSV</button><button onClick={exportJson} className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold">Export JSON</button></div>}>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-5">
          <TimeFilter value={filters.time_range} onChange={(value) => changeFilter(setFilters, setPage, 'time_range', value)} start={filters.start} end={filters.end} onStartChange={(value) => changeFilter(setFilters, setPage, 'start', value)} onEndChange={(value) => changeFilter(setFilters, setPage, 'end', value)} />
          <label className="text-xs font-semibold text-slate-500">Environment
            <select value={filters.environment} onChange={(event) => changeFilter(setFilters, setPage, 'environment', event.target.value)} className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm">
              <option value="">All</option>{['DEVELOPMENT', 'QA', 'STAGING', 'PRODUCTION'].map((value) => <option key={value}>{value}</option>)}
            </select>
          </label>
          <label className="text-xs font-semibold text-slate-500">Log level
            <select value={filters.level} onChange={(event) => changeFilter(setFilters, setPage, 'level', event.target.value)} className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm">
              <option value="">All levels</option>{['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'].map((value) => <option key={value}>{value}</option>)}
            </select>
          </label>
          <FilterInput label="Service" value={filters.service} placeholder="Service" onChange={(value) => changeFilter(setFilters, setPage, 'service', value)} />
          <FilterInput label="Agent" value={filters.agent} placeholder="Agent name" onChange={(value) => changeFilter(setFilters, setPage, 'agent', value)} />
          <FilterInput label="Tool" value={filters.tool} placeholder="Tool name" onChange={(value) => changeFilter(setFilters, setPage, 'tool', value)} />
          <FilterInput label="Model" value={filters.model} placeholder="Model name" onChange={(value) => changeFilter(setFilters, setPage, 'model', value)} />
          <FilterInput label="Status" value={filters.status} placeholder="SUCCESS / ERROR" onChange={(value) => changeFilter(setFilters, setPage, 'status', value)} />
          <label className="text-xs font-semibold text-slate-500">Search
            <input value={filters.q} onChange={(event) => changeFilter(setFilters, setPage, 'q', event.target.value)} placeholder="Message / endpoint" className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" />
          </label>
          <label className="text-xs font-semibold text-slate-500">Trace ID
            <input value={filters.trace_id} onChange={(event) => changeFilter(setFilters, setPage, 'trace_id', event.target.value)} placeholder="Filter trace" className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" />
          </label>
          <FilterInput label="Request ID" value={filters.request_id} placeholder="Request ID" onChange={(value) => changeFilter(setFilters, setPage, 'request_id', value)} />
          <FilterInput label="Session ID" value={filters.session_id} placeholder="Session ID" onChange={(value) => changeFilter(setFilters, setPage, 'session_id', value)} />
          <FilterInput label="Endpoint" value={filters.endpoint} placeholder="/api/…" onChange={(value) => changeFilter(setFilters, setPage, 'endpoint', value)} />
          <label className="text-xs font-semibold text-slate-500">Sort
            <select value={`${filters.sort}:${filters.order}`} onChange={(event) => {
              const [sort, order] = event.target.value.split(':');
              setFilters((current) => ({ ...current, sort, order }));
            }} className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm">
              <option value="timestamp:desc">Newest first</option><option value="timestamp:asc">Oldest first</option><option value="level:asc">Level</option><option value="latency_ms:desc">Slowest first</option><option value="status:asc">Status</option>
            </select>
          </label>
          <label className="flex items-center gap-2 self-end rounded-lg bg-slate-50 p-2 text-sm text-slate-600"><input type="checkbox" checked={refresh} onChange={(event) => setRefresh(event.target.checked)} /> Auto refresh 15s</label>
        </div>
      </Panel>

      <div className="mt-5">
        <Panel title={`Events · ${data?.total ?? '—'} total`}>
          <DataTable headers={['Timestamp', 'Level', 'Service / Environment', 'Trace ID', 'Agent / Tool', 'Endpoint', 'Message', 'Latency', 'Status']}>
            {(data?.items || []).map((item) => (
              <tr key={item.id} className="hover:bg-slate-50">
                <TableCell className="whitespace-nowrap text-xs">{new Date(item.timestamp).toLocaleString()}</TableCell>
                <TableCell><Status value={item.level} /></TableCell>
                <TableCell><span className="font-medium text-slate-800">{item.service}</span><span className="mt-1 block text-xs">{item.environment}</span></TableCell>
                <TableCell>{item.trace_id ? <Link href={traceUrl(item.trace_id)} className="max-w-32 truncate font-mono text-xs text-cyan-700 hover:underline">{item.trace_id}</Link> : '—'}</TableCell>
                <TableCell className="text-xs">{item.agent_name || item.tool_name || item.model_name || '—'}</TableCell>
                <TableCell className="max-w-32 truncate text-xs">{item.endpoint || '—'}</TableCell>
                <TableCell><button onClick={() => showDetails(item.id)} className="max-w-64 truncate text-left text-xs text-slate-700 hover:text-cyan-700">{item.message}</button></TableCell>
                <TableCell className="whitespace-nowrap text-xs">{item.latency_ms == null ? '—' : `${item.latency_ms.toFixed(1)} ms`}</TableCell>
                <TableCell><Status value={item.status} /></TableCell>
              </tr>
            ))}
          </DataTable>
          {!data?.items.length && <p className="py-8 text-center text-sm text-slate-400">No logs match these filters.</p>}
          <Pagination page={page} perPage={data?.per_page || 50} total={data?.total || 0} onChange={setPage} />
        </Panel>
      </div>

      {selected && <div className="fixed inset-0 z-20 grid place-items-center bg-slate-950/40 p-4" onClick={() => setSelected(null)}>
        <section className="max-h-[85vh] w-full max-w-3xl overflow-auto rounded-2xl bg-white p-5 shadow-xl" onClick={(event) => event.stopPropagation()}>
          <div className="mb-3 flex items-center justify-between"><h2 className="font-semibold">Structured log</h2><button onClick={() => setSelected(null)} className="rounded-lg px-3 py-1 text-sm hover:bg-slate-100">Close</button></div>
          {typeof selected.trace_id === 'string' && <Link href={traceUrl(selected.trace_id)} className="mb-3 inline-block text-sm font-semibold text-cyan-700">Open correlated trace →</Link>}
          <pre className="overflow-auto rounded-xl bg-slate-950 p-4 text-xs leading-5 text-emerald-100">{JSON.stringify(selected, null, 2)}</pre>
        </section>
      </div>}
    </Shell>
  );
}

function changeFilter(
  setFilters: React.Dispatch<React.SetStateAction<{
    time_range: string; start: string; end: string; environment: string; level: string;
    service: string; agent: string; tool: string; model: string; status: string;
    request_id: string; trace_id: string; session_id: string; endpoint: string;
    q: string; sort: string; order: string;
  }>>,
  setPage: (page: number) => void, key: string, value: string,
) {
  setFilters((current) => ({ ...current, [key]: value }));
  setPage(1);
}

function FilterInput({ label, value, placeholder, onChange }: { label: string; value: string; placeholder: string; onChange: (value: string) => void }) {
  return <label className="text-xs font-semibold text-slate-500">{label}<input value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" /></label>;
}

function Pagination({ page, perPage, total, onChange }: { page: number; perPage: number; total: number; onChange: (page: number) => void }) {
  return <div className="mt-4 flex items-center justify-between text-xs text-slate-500">
    <span>Showing {total ? (page - 1) * perPage + 1 : 0}–{Math.min(page * perPage, total)} of {total}</span>
    <div className="flex gap-2"><button disabled={page <= 1} onClick={() => onChange(page - 1)} className="rounded-lg border px-3 py-2 disabled:opacity-40">Previous</button><button disabled={page * perPage >= total} onClick={() => onChange(page + 1)} className="rounded-lg border px-3 py-2 disabled:opacity-40">Next</button></div>
  </div>;
}

function csvEscape(value: string) {
  return `"${value.replaceAll('"', '""')}"`;
}

function download(filename: string, content: string, type: string) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}
