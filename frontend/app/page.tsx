'use client';

import { useState } from 'react';
import Link from 'next/link';
import { apiUrl } from '../lib/api';

export default function Page() {
  const [supplierId, setSupplierId] = useState('SUP001');
  const [purchaseOrderId, setPurchaseOrderId] = useState('PO10025');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);

  async function analyzeRisk() {
    setLoading(true);
    try {
      const res = await fetch(apiUrl('/api/risk/classify'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_query: `Classify delay risk for supplier ${supplierId} and purchase order ${purchaseOrderId}.`,
          supplier_id: supplierId,
          purchase_order_id: purchaseOrderId,
        }),
      });

      if (!res.ok) {
        let message = `Request failed with status ${res.status}`;
        try {
          const errData = await res.json();
          if (errData?.detail) {
            message = typeof errData.detail === 'string' ? errData.detail : JSON.stringify(errData.detail);
          } else if (errData?.message) {
            message = errData.message;
          }
        } catch {
          try {
            const text = await res.text();
            if (text) message = text;
          } catch {
            // Ignore non-JSON fallback parsing errors.
          }
        }
        throw new Error(message);
      }

      const data = await res.json();
      setResult(data);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unable to connect to backend service.';
      setResult({
        final_response: `Unable to complete classification: ${message}`,
        errors: [message],
      });
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-slate-100 p-8">
      <div className="mx-auto max-w-6xl space-y-6">
        <header className="rounded-xl bg-slate-900 p-6 text-white shadow-xl">
          <div className="flex flex-wrap items-center justify-between gap-5">
            <div>
              <p className="text-sm uppercase tracking-[0.2em] text-cyan-300">Retail Supply Chain</p>
              <h1 className="mt-3 text-3xl font-bold">Supplier Delay Risk Classification</h1>
              <p className="mt-2 text-slate-300">Multi-agent workflow using supplier data, shipment indicators, inventory impact, and policy retrieval.</p>
            </div>
            <nav className="flex flex-wrap gap-2" aria-label="Observability">
              {['Overview', 'Logs', 'Metrics', 'Traces', 'Drift'].map((item) => <Link key={item} href={item === 'Overview' ? '/' : `/${item.toLowerCase()}`} className="rounded-lg border border-slate-700 px-3 py-2 text-sm font-semibold text-white hover:border-cyan-400 hover:text-cyan-200">{item}</Link>)}
            </nav>
          </div>
        </header>

        <section className="grid gap-6 md:grid-cols-[1fr_2fr]">
          <div className="rounded-xl bg-white p-6 shadow">
            <h2 className="text-xl font-semibold">Risk Analysis</h2>
            <div className="mt-4 space-y-4">
              <label className="block">
                <span className="mb-1 block text-sm font-medium text-slate-700">Supplier ID</span>
                <input
                  value={supplierId}
                  onChange={(e) => setSupplierId(e.target.value)}
                  className="w-full rounded border border-slate-300 p-2"
                />
              </label>
              <label className="block">
                <span className="mb-1 block text-sm font-medium text-slate-700">Purchase Order ID</span>
                <input
                  value={purchaseOrderId}
                  onChange={(e) => setPurchaseOrderId(e.target.value)}
                  className="w-full rounded border border-slate-300 p-2"
                />
              </label>
              <button
                onClick={analyzeRisk}
                className="w-full rounded bg-blue-600 px-4 py-2 font-semibold text-white hover:bg-blue-500 disabled:opacity-50"
                disabled={loading}
              >
                {loading ? 'Analyzing...' : 'Analyze Risk'}
              </button>
            </div>
          </div>

          <div className="rounded-xl bg-white p-6 shadow">
            <h2 className="text-xl font-semibold">Workflow Overview</h2>
            <div className="mt-4 grid gap-2 md:grid-cols-3">
              {['Triage', 'Supplier Retrieval', 'Performance', 'Shipment', 'Inventory', 'RAG', 'Risk Classification', 'Validation', 'Response'].map((step) => (
                <div key={step} className="rounded border border-slate-200 bg-slate-50 p-2 text-center text-sm font-medium text-slate-700">
                  {step}
                </div>
              ))}
            </div>

            {result && (
              <div className="mt-6 rounded-lg border border-slate-200 bg-slate-50 p-4">
                <h3 className="text-lg font-semibold">Classification Summary</h3>
                <p className="mt-2 whitespace-pre-wrap text-sm text-slate-700">{result.final_response || 'No response available.'}</p>
                {result.risk_classification && (
                  <div className="mt-4 grid gap-3 md:grid-cols-2">
                    <div className="rounded bg-slate-900 p-3 text-white">
                      <div className="text-xs uppercase tracking-wide text-slate-300">Risk Class</div>
                      <div className="mt-1 text-2xl font-bold">{result.risk_classification.risk_class}</div>
                    </div>
                    <div className="rounded bg-slate-900 p-3 text-white">
                      <div className="text-xs uppercase tracking-wide text-slate-300">Risk Score</div>
                      <div className="mt-1 text-2xl font-bold">{result.risk_classification.risk_score}</div>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </section>
      </div>
    </main>
  );
}
