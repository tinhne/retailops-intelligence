import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";

import { Providers } from "./providers";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });

export const metadata: Metadata = {
  title: {
    default: "RetailOps Intelligence",
    template: "%s · RetailOps",
  },
  description:
    "E-commerce operations and decision intelligence: detect, prioritise and resolve operational exceptions.",
};

export const viewport: Viewport = {
  themeColor: "#f8f9fa",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="min-h-dvh">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
