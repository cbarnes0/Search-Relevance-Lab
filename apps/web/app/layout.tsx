import type { Metadata } from "next";
import Link from "next/link";

import "./globals.css";

export const metadata: Metadata = {
  title: "Search Relevance Lab",
  description: "Multi-backend search evaluation platform",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <header className="app-header">
          <Link href="/" className="app-header__brand">
            🔍 Search Relevance Lab
          </Link>
          <nav className="app-header__nav">
            <Link href="/">Search</Link>
            <Link href="/runs">Runs</Link>
          </nav>
        </header>
        {children}
      </body>
    </html>
  );
}
