import type { Metadata } from "next";
import { SSRProvider } from "@fluentui/react-components";

import { Nav } from "@/components/nav";
import { LocaleProvider } from "@/lib/i18n";

import "./globals.css";

export const metadata: Metadata = { title: "Decision Layer", description: "Analysis methods and recipes over a semantic layer" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <SSRProvider>
          <LocaleProvider>
            <div className="app-shell">
              <Nav />
              <main className="app-main">{children}</main>
            </div>
          </LocaleProvider>
        </SSRProvider>
      </body>
    </html>
  );
}
