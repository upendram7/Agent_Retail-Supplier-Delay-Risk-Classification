import './globals.css';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Retail Supplier Risk Observability',
  description: 'Risk classification and persisted agent observability dashboards',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
