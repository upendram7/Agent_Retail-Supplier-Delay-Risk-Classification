'use client';

import { useEffect, useState } from 'react';
import {
  ApiList, Card, DataTable, ErrorNotice, LineChart, Panel, Shell, Status, TableCell,
  TimeFilter, api,
} from '../../components/observability';

type DriftItem = {
  id: number; timestamp: string; category: string; feature_name?: string;
  baseline_value?: number; current_value?: number; drift_score?: number;
  method?: string; status: string;
};
type DriftSummary = { overall_status: string; categories: Record<string, { score: number; max_score: number; observations: number }>; series: Array<{ bucket: string; value: number | null }> };

const categories = [
  ['data', 'Data drift'], ['model', 'Model drift'], ['prediction', 'Prediction drift'],
  ['concept', 'Concept drift'], ['prompt', 'Prompt drift'], ['retrieval', 'Retrieval drift'],
] as const;

export default function DriftPage() {
  const [timeRange, setTimeRange] = useState('30d');
  const [environment, setEnvironment] = useState('');
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [summary, setSummary] = useState<DriftSummary | null>(null);
  const [items, setItems] = useState<DriftItem[]>([]);
  const [error, setError] = useState('');
  useEffect(() => {
    const params = new URLSearchParams({ time_range: timeRange });
    if (environment) params.set('environment', environment);
    if (timeRange === 'custom' && start) params.set('start', start);
    if (timeRange === 'custom' && end) params.set('end', end);
    Promise.all([
      api<DriftSummary>(`/api/drift?${params.toString()}`),
      ...categories.map(([category]) => api<ApiList<DriftItem>>(`/api/drift/${category}?${params.toString()}&per_page=30`)),
    ]).then(([overview, ...results]) => {
      setSummary(overview);
      setItems(results.flatMap((result) => result.items));
      setError('');
    }).catch((reason: Error) => setError(reason.message));
  }, [timeRange, environment, start, end]);

  const colors: Record<string, string> = { NORMAL: 'green', WARNING: 'amber', CRITICAL: 'red' };
  return <Shell title="Drift monitoring" description="Track feature, model, prediction, concept, prompt, and retrieval changes. Threshold colors follow PSI guidance: under 0.10 stable, up to 0.25 warning, above 0.25 critical.">
    <ErrorNotice message={error} />
    <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
      <label className="flex items-center gap-2 text-xs font-semibold text-slate-500">Environment
        <select value={environment} onChange={(event) => setEnvironment(event.target.value)} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800">
          <option value="">All environments</option>{['DEVELOPMENT', 'QA', 'STAGING', 'PRODUCTION'].map((value) => <option key={value}>{value}</option>)}
        </select>
      </label>
      <TimeFilter value={timeRange} onChange={setTimeRange} start={start} end={end} onStartChange={setStart} onEndChange={setEnd} />
    </div>
    {summary && <>
      <div className="mb-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Card title="Overall drift status" value={<Status value={summary.overall_status} />} detail="Maximum observed score in the selected range" tone={colors[summary.overall_status] as 'green' | 'amber' | 'red'} />
        {categories.map(([key, label]) => {
          const row = summary.categories[key];
          const score = row?.max_score;
          const status = score == null ? 'UNKNOWN' : score < 0.1 ? 'NORMAL' : score <= 0.25 ? 'WARNING' : 'CRITICAL';
          return <Card key={key} title={label} value={<Status value={status} />} detail={`${row?.observations || 0} observations · max score ${score == null ? '—' : score.toFixed(3)}`} tone={colors[status] as 'green' | 'amber' | 'red' || 'slate'} />;
        })}
      </div>
      <div className="mb-5 grid gap-5 xl:grid-cols-2">
        <Panel title="Drift score over time"><LineChart points={summary.series || []} color="#e11d48" valueLabel="Drift score" /></Panel>
        <Panel title="Baseline vs current observations">
          {items.filter((item) => item.baseline_value != null || item.current_value != null).slice(0, 8).map((item) => {
            const baseline = Number(item.baseline_value || 0);
            const current = Number(item.current_value || 0);
            const max = Math.max(baseline, current, 0.01);
            return <div key={item.id} className="mb-3 grid grid-cols-[120px_1fr_130px] items-center gap-3 text-xs">
              <span className="truncate text-slate-600">{item.feature_name || item.category}</span>
              <span className="flex h-5 overflow-hidden rounded bg-slate-100">
                <i className="h-full bg-blue-400" style={{ width: `${(baseline / max) * 50}%` }} />
                <i className="h-full bg-rose-400" style={{ width: `${(current / max) * 50}%` }} />
              </span>
              <span className="text-right text-slate-500">base {baseline.toFixed(2)} · now {current.toFixed(2)}</span>
            </div>;
          })}
          <div className="mt-4 flex gap-4 text-[10px] text-slate-500"><span><i className="mr-1 inline-block h-2 w-2 bg-blue-400" />Baseline</span><span><i className="mr-1 inline-block h-2 w-2 bg-rose-400" />Current</span></div>
          {!items.some((item) => item.baseline_value != null || item.current_value != null) && <p className="text-sm text-slate-400">No comparable distributions in this range.</p>}
        </Panel>
      </div>
      <Panel title="Drift observations">
        <DataTable headers={['Timestamp', 'Category', 'Feature', 'Method', 'Baseline', 'Current', 'Score', 'Status']}>
          {items.slice(0, 100).map((item) => <tr key={`${item.category}-${item.id}`} className="hover:bg-slate-50">
            <TableCell className="whitespace-nowrap text-xs">{new Date(item.timestamp).toLocaleString()}</TableCell>
            <TableCell className="capitalize">{item.category}</TableCell>
            <TableCell>{item.feature_name || '—'}</TableCell>
            <TableCell>{item.method || '—'}</TableCell>
            <TableCell>{item.baseline_value == null ? '—' : Number(item.baseline_value).toFixed(3)}</TableCell>
            <TableCell>{item.current_value == null ? '—' : Number(item.current_value).toFixed(3)}</TableCell>
            <TableCell>{item.drift_score == null ? '—' : Number(item.drift_score).toFixed(3)}</TableCell>
            <TableCell><Status value={item.status} /></TableCell>
          </tr>)}
        </DataTable>
        {!items.length && <p className="py-8 text-center text-sm text-slate-400">No drift observations in this period.</p>}
      </Panel>
    </>}
  </Shell>;
}
