'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { ReactNode } from 'react';

export const TIME_RANGES = [
  ['15m', 'Last 15 minutes'],
  ['1h', 'Last hour'],
  ['6h', 'Last 6 hours'],
  ['24h', 'Last 24 hours'],
  ['7d', 'Last 7 days'],
  ['30d', 'Last 30 days'],
  ['custom', 'Custom range'],
];

export type ApiList<T> = { items: T[]; page: number; per_page: number; total: number; summary?: Record<string, number | string | null> };

export async function api<T>(path: string): Promise<T> {
  const response = await fetch(path, { cache: 'no-store' });
  if (!response.ok) {
    throw new Error(`Observability API returned ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function queryString(values: Record<string, string | number | undefined>): string {
  const params = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => {
    if (value !== undefined && value !== '') params.set(key, String(value));
  });
  return params.toString();
}

export function Shell({ title, description, children }: { title: string; description: string; children: ReactNode }) {
  const pathname = usePathname();
  const tabs = [
    ['Overview', '/'],
    ['Logs', '/logs'],
    ['Metrics', '/metrics'],
    ['Traces', '/traces'],
    ['Drift', '/drift'],
  ];
  return (
    <main className="min-h-screen bg-[#f4f6f9] text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-[1440px] flex-wrap items-center justify-between gap-5 px-5 py-5 lg:px-8">
          <Link href="/metrics" className="flex items-center gap-3">
            <span className="grid h-10 w-10 place-items-center rounded-xl bg-slate-950 text-sm font-bold text-cyan-300">OR</span>
            <span>
              <span className="block text-sm font-bold tracking-tight">RETAIL OBSERVABILITY</span>
              <span className="block text-xs text-slate-500">Supplier Delay Risk Agent</span>
            </span>
          </Link>
          <nav className="flex gap-1 overflow-x-auto rounded-xl bg-slate-100 p-1" aria-label="Observability">
            {tabs.map(([label, href]) => {
              const active = pathname === href || pathname.startsWith(`${href}/`);
              return (
                <Link key={`${label}-${href}`} href={href} className={`whitespace-nowrap rounded-lg px-3 py-2 text-sm font-semibold ${active ? 'bg-white text-slate-950 shadow-sm' : 'text-slate-500 hover:text-slate-900'}`}>
                  {label}
                </Link>
              );
            })}
          </nav>
          <div className="flex items-center gap-2 text-xs font-medium text-emerald-700">
            <span className="h-2 w-2 rounded-full bg-emerald-500" /> API connected
          </div>
        </div>
      </header>
      <div className="mx-auto max-w-[1440px] px-5 py-8 lg:px-8">
        <div className="mb-7">
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-cyan-700">Observability / {title}</p>
          <h1 className="mt-2 text-3xl font-bold tracking-tight">{title}</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-500">{description}</p>
        </div>
        {children}
      </div>
    </main>
  );
}

export function TimeFilter({
  value, onChange, start, end, onStartChange, onEndChange,
}: {
  value: string; onChange: (value: string) => void; start?: string; end?: string;
  onStartChange?: (value: string) => void; onEndChange?: (value: string) => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2 text-xs font-semibold text-slate-500">
      <label className="flex items-center gap-2">Time range
        <select value={value} onChange={(event) => {
          const next = event.target.value;
          if (next === 'custom') {
            onStartChange?.(start || localDateTime(-24 * 60 * 60 * 1000));
            onEndChange?.(end || localDateTime(0));
          }
          onChange(next);
        }} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800">
          {TIME_RANGES.map(([key, label]) => <option key={key} value={key}>{label}</option>)}
        </select>
      </label>
      {value === 'custom' && onStartChange && onEndChange && <>
        <input aria-label="Custom start time" type="datetime-local" value={start || ''} onChange={(event) => onStartChange(event.target.value)} className="rounded-lg border border-slate-200 bg-white px-2 py-2 text-xs text-slate-700" />
        <input aria-label="Custom end time" type="datetime-local" value={end || ''} onChange={(event) => onEndChange(event.target.value)} className="rounded-lg border border-slate-200 bg-white px-2 py-2 text-xs text-slate-700" />
      </>}
    </div>
  );
}

function localDateTime(offsetMs: number): string {
  const date = new Date(Date.now() + offsetMs);
  date.setMinutes(date.getMinutes() - date.getTimezoneOffset());
  return date.toISOString().slice(0, 16);
}

export function Card({ title, value, detail, tone = 'slate' }: { title: string; value: ReactNode; detail?: string; tone?: 'slate' | 'green' | 'amber' | 'red' | 'blue' }) {
  const tones = {
    slate: 'border-slate-200 bg-white',
    green: 'border-emerald-200 bg-emerald-50/50',
    amber: 'border-amber-200 bg-amber-50/60',
    red: 'border-rose-200 bg-rose-50/60',
    blue: 'border-blue-200 bg-blue-50/60',
  };
  return (
    <section className={`rounded-2xl border p-5 shadow-sm ${tones[tone]}`}>
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{title}</p>
      <p className="mt-3 text-2xl font-bold tracking-tight text-slate-950">{value}</p>
      {detail && <p className="mt-2 text-xs text-slate-500">{detail}</p>}
    </section>
  );
}

export function Panel({ title, action, children }: { title: string; action?: ReactNode; children: ReactNode }) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex items-center justify-between gap-3">
        <h2 className="font-semibold">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}

export function Status({ value }: { value?: string | number | null }) {
  const status = String(value || 'UNKNOWN').toUpperCase();
  const tone = ['SUCCESS', 'NORMAL', 'ALLOW', 'APPROVED', 'HEALTHY'].includes(status)
    ? 'bg-emerald-100 text-emerald-800'
    : ['WARNING', 'AMBER', 'PENDING', 'RUNNING'].includes(status)
      ? 'bg-amber-100 text-amber-800'
      : ['ERROR', 'CRITICAL', 'BLOCK', 'FAILED', 'REJECTED'].includes(status)
        ? 'bg-rose-100 text-rose-800'
        : 'bg-slate-100 text-slate-700';
  return <span className={`inline-flex rounded-full px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide ${tone}`}>{status}</span>;
}

export function LineChart({ points, color = '#0891b2', valueLabel }: { points: Array<{ bucket: string; value: number | null }>; color?: string; valueLabel?: string }) {
  const values = points.map((point) => Number(point.value) || 0);
  const max = Math.max(...values, 1);
  const width = 700;
  const height = 170;
  const coordinate = points.map((point, index) => {
    const x = points.length <= 1 ? width / 2 : (index / (points.length - 1)) * width;
    const y = height - ((Number(point.value) || 0) / max) * (height - 24) - 12;
    return `${x},${y}`;
  }).join(' ');
  return (
    <div>
      <svg viewBox={`0 0 ${width} ${height}`} className="h-44 w-full overflow-visible" role="img" aria-label={valueLabel || 'Metric trend'}>
        {[0, 1, 2, 3].map((row) => <line key={row} x1="0" x2={width} y1={row * 48 + 10} y2={row * 48 + 10} stroke="#e2e8f0" strokeDasharray="3 5" />)}
        {points.length > 0 && <polyline points={coordinate} fill="none" stroke={color} strokeWidth="3" strokeLinejoin="round" strokeLinecap="round" />}
        {points.map((point, index) => {
          const x = points.length <= 1 ? width / 2 : (index / (points.length - 1)) * width;
          const y = height - ((Number(point.value) || 0) / max) * (height - 24) - 12;
          return <circle key={`${point.bucket}-${index}`} cx={x} cy={y} r="3.5" fill={color}><title>{`${point.bucket}: ${point.value ?? 0}`}</title></circle>;
        })}
      </svg>
      {points.length === 0 && <p className="text-sm text-slate-400">No measurements in this range.</p>}
      {points.length > 0 && (
        <div className="flex justify-between text-[10px] text-slate-400">
          <span>{points[0].bucket}</span><span>{points[points.length - 1].bucket}</span>
        </div>
      )}
    </div>
  );
}

export function ErrorNotice({ message }: { message?: string }) {
  if (!message) return null;
  return <div role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">{message}</div>;
}

export function Loading({ label = 'Loading observability data…' }: { label?: string }) {
  return <div className="rounded-xl border border-slate-200 bg-white px-4 py-8 text-center text-sm text-slate-500">{label}</div>;
}

export function DataTable({ headers, children }: { headers: string[]; children: ReactNode }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[720px] border-collapse text-left text-sm">
        <thead><tr>{headers.map((header) => <th key={header} className="border-b border-slate-100 px-3 py-3 text-[10px] font-bold uppercase tracking-wide text-slate-400">{header}</th>)}</tr></thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}

export function TableCell({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <td className={`border-b border-slate-50 px-3 py-3 align-top text-slate-600 ${className}`}>{children}</td>;
}

export function formatNumber(value: unknown, digits = 0): string {
  const number = Number(value);
  return Number.isFinite(number) ? number.toLocaleString(undefined, { maximumFractionDigits: digits }) : '—';
}

export function traceUrl(traceId?: string | null): string {
  return traceId ? `/traces/${encodeURIComponent(traceId)}` : '/traces';
}
