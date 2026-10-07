'use client';

import { useEffect, useState } from 'react';
import {
  api, Card, ErrorNotice, LineChart, Loading, Panel, Shell, TimeFilter, formatNumber, queryString,
} from '../../components/observability';

type CardTone = 'slate' | 'green' | 'amber' | 'red' | 'blue';
type Overview = {
  requests: { total: number; successful: number; failed: number; avg_latency: number; success_rate: number };
  llm: { calls: number; tokens: number; cost: number; avg_latency: number };
  agents: { runs: number; successful: number };
  tools: { calls: number; failed: number };
  rag: { calls: number; avg_similarity: number | null; empty: number };
  active_alerts: number;
  guardrail_blocks: number;
  drift_score: number | null;
  system: { cpu_percent?: number; memory_percent?: number; database_size_bytes?: number };
  series: Record<string, Array<{ bucket: string; value: number | null }>>;
};

export default function MetricsPage() {
  const [timeRange, setTimeRange] = useState('24h');
  const [environment, setEnvironment] = useState('');
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [data, setData] = useState<Overview | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    const query = queryString({ time_range: timeRange, environment, start: timeRange === 'custom' ? start : undefined, end: timeRange === 'custom' ? end : undefined });
    api<Overview>(`/api/observability/overview?${query}`)
      .then((result) => { if (!cancelled) { setData(result); setError(''); } })
      .catch((reason: Error) => { if (!cancelled) setError(reason.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [timeRange, environment, start, end]);

  const cards: Array<[string, string, string, CardTone]> = data ? [
    ['Requests', formatNumber(data.requests.total), `${formatNumber(data.requests.successful)} successful · ${formatNumber(data.requests.failed)} failed`, 'blue'],
    ['Success rate', `${formatNumber(data.requests.success_rate, 1)}%`, `${formatNumber(data.requests.avg_latency, 1)} ms average latency`, data.requests.success_rate > 95 ? 'green' : 'amber'],
    ['LLM calls', formatNumber(data.llm.calls), `${formatNumber(data.llm.tokens)} tokens recorded`, 'slate'],
    ['Estimated cost', `$${formatNumber(data.llm.cost, 4)}`, `Average LLM latency ${formatNumber(data.llm.avg_latency, 1)} ms`, 'slate'],
    ['Agent runs', formatNumber(data.agents.runs), `${formatNumber(data.agents.successful)} successful`, 'slate'],
    ['Tool calls', formatNumber(data.tools.calls), `${formatNumber(data.tools.failed)} failed`, data.tools.failed ? 'amber' : 'green'],
    ['RAG retrieval', formatNumber(data.rag.calls), `${formatNumber(data.rag.avg_similarity, 3)} mean similarity`, 'slate'],
    ['Guardrail blocks', formatNumber(data.guardrail_blocks), 'Input and tool policy decisions', data.guardrail_blocks ? 'amber' : 'green'],
    ['Active alerts', formatNumber(data.active_alerts), 'Threshold-based monitoring', data.active_alerts ? 'red' : 'green'],
    ['Drift score', formatNumber(data.drift_score, 3), 'Maximum observed drift score', Number(data.drift_score) > 0.25 ? 'red' : 'green'],
    ['CPU load', data.system.cpu_percent == null ? '—' : `${formatNumber(data.system.cpu_percent, 1)}%`, `Process memory ${formatNumber(data.system.memory_percent, 1)}%`, 'slate'],
    ['Database size', `${formatNumber(Number(data.system.database_size_bytes) / (1024 * 1024), 2)} MB`, 'SQLite observability store', 'slate'],
  ] : [];

  return (
    <Shell title="Observability overview" description="Live application, agent, LLM, tool, retrieval, infrastructure, and guardrail health—backed by persisted SQLite events.">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-xs text-slate-500"><span className="h-2 w-2 rounded-full bg-emerald-500" /> Seeded demo + real request telemetry</div>
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 text-xs font-semibold text-slate-500">Environment
            <select value={environment} onChange={(event) => setEnvironment(event.target.value)} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800">
              <option value="">All environments</option>
              {['DEVELOPMENT', 'QA', 'STAGING', 'PRODUCTION'].map((item) => <option key={item}>{item}</option>)}
            </select>
          </label>
          <TimeFilter value={timeRange} onChange={setTimeRange} start={start} end={end} onStartChange={setStart} onEndChange={setEnd} />
        </div>
      </div>
      <ErrorNotice message={error} />
      {loading && !data ? <Loading /> : data && (
        <>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {cards.map(([title, value, detail, tone]) => <Card key={title} title={title} value={value} detail={detail} tone={tone} />)}
          </div>
          <div className="mt-5 grid gap-5 xl:grid-cols-2">
            <Panel title="Requests over time"><LineChart points={data.series.requests || []} color="#2563eb" valueLabel="Requests" /></Panel>
            <Panel title="Request latency"><LineChart points={data.series.latency || []} color="#0891b2" valueLabel="Average request latency" /></Panel>
            <Panel title="Token usage"><LineChart points={data.series.tokens || []} color="#7c3aed" valueLabel="Tokens" /></Panel>
            <Panel title="Estimated cost"><LineChart points={data.series.cost || []} color="#059669" valueLabel="Estimated cost" /></Panel>
            <Panel title="Drift trend"><LineChart points={data.series.drift || []} color="#e11d48" valueLabel="Average drift score" /></Panel>
            <Panel title="Operational status">
              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-xl bg-emerald-50 p-4"><p className="text-xs text-slate-500">RAG no-result rate</p><p className="mt-1 text-xl font-bold">{data.rag.calls ? formatNumber((Number(data.rag.empty) / Number(data.rag.calls)) * 100, 1) : '0'}%</p></div>
                <div className="rounded-xl bg-blue-50 p-4"><p className="text-xs text-slate-500">Tool failure rate</p><p className="mt-1 text-xl font-bold">{data.tools.calls ? formatNumber((Number(data.tools.failed) / Number(data.tools.calls)) * 100, 1) : '0'}%</p></div>
                <div className="rounded-xl bg-slate-50 p-4"><p className="text-xs text-slate-500">Database size</p><p className="mt-1 text-xl font-bold">{formatNumber(Number(data.system.database_size_bytes) / (1024 * 1024), 2)} MB</p></div>
                <div className="rounded-xl bg-slate-50 p-4"><p className="text-xs text-slate-500">Infrastructure samples</p><p className="mt-1 text-xl font-bold">{data.system.cpu_percent == null ? 'Unavailable' : 'Collecting'}</p></div>
              </div>
            </Panel>
          </div>
        </>
      )}
    </Shell>
  );
}
