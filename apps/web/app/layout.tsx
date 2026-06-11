import type { Metadata } from "next";
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
      <body>{children}</body>
    </html>
  );
}
