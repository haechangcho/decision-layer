"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { BookOpen, Database, History, Layers3, LayoutGrid, ShieldCheck, Workflow } from "lucide-react";

import { getToken, setToken } from "@/lib/api";
import { LOCALES, Locale, useLocale, useT } from "@/lib/i18n";

const LINKS = [["/recipes", "분석하기", BookOpen], ["/catalog", "지표 탐색", LayoutGrid], ["/methods", "Methods", Workflow], ["/runs", "Runs", History]] as const;

export function Nav() {
  const path = usePathname();
  const [token, setTok] = useState("");
  const [editing, setEditing] = useState(false);
  const t = useT();
  const { locale, setLocale } = useLocale();
  useEffect(() => setTok(getToken()), []);
  return <>
    <header className="app-topbar">
      <Link className="app-brand" href="/" aria-label="Decision Layer home"><span className="app-brand-mark"><Layers3 size={19} /></span><strong>Decision Layer</strong></Link>
      <span className="app-topbar-divider" />
      <span className="app-workspace-label">Analytics workspace</span>
      <span className="app-topbar-spacer" />
      {editing ? (
        <form onSubmit={(e) => { e.preventDefault(); setToken(token); setEditing(false); location.reload(); }} className="app-token-form">
          <input type="password" aria-label={t("Cube user token")} placeholder={t("Cube user token")} value={token} onChange={(e) => setTok(e.target.value)} />
          <button type="submit">{t("Save")}</button>
        </form>
      ) : <button className="app-credentials" onClick={() => setEditing(true)} title={token ? t("Using a token") : t("Cube user token required")}><ShieldCheck size={15} />{token ? t("Using a token") : t("Cube user token required")}</button>}
      <select className="app-locale" value={locale} onChange={(e) => setLocale(e.target.value as Locale)} aria-label="language">
        {LOCALES.map((l) => <option key={l} value={l}>{l}</option>)}
      </select>
    </header>
    <aside className="app-sidebar">
      <div className="app-sidebar-workspace"><span><Database size={17} /></span><div><strong>Workspace</strong><small>Semantic analytics</small></div></div>
      <div className="app-nav-label">WORKSPACE</div>
      <nav aria-label="Main navigation" className="app-nav-links">
        {LINKS.map(([href, label, Icon]) => <Link key={href} href={href} className={path === href || path.startsWith(`${href}/`) ? "active" : ""} aria-current={path === href || path.startsWith(`${href}/`) ? "page" : undefined}><Icon size={17} /><span>{label}</span></Link>)}
      </nav>
      <div className="app-sidebar-bottom"><div className="app-nav-label">SETTINGS</div><Link href="/sources" className={path.startsWith("/sources") ? "active" : ""} aria-current={path.startsWith("/sources") ? "page" : undefined}><Database size={17} /><span>Data source</span></Link><small>Cube semantic layer</small></div>
    </aside>
  </>;
}
