import './globals.css';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Supplier Delay Risk Classification',
  description: 'Agentic AI demo for retail supplier delay risk classification',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
