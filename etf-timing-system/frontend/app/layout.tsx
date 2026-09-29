import type { Metadata } from 'next';
import './globals.css';

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL
  ?? (process.env.VERCEL_PROJECT_PRODUCTION_URL
    ? `https://${process.env.VERCEL_PROJECT_PRODUCTION_URL}`
    : 'http://localhost:3000');

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: 'ETF 择时系统 · 数据观察',
  description: '面向主观操盘者的 A 股 ETF 市场与标的原始数据看板。',
  openGraph: {
    title: 'ETF 择时系统',
    description: '市场与 ETF 原始数据观察',
    images: ['/og.png'],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'ETF 择时系统',
    description: '市场与 ETF 原始数据观察',
    images: ['/og.png'],
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
