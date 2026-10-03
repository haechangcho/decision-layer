"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { BookOpen, Database, History, Layers3, LayoutGrid, ShieldCheck, Workflow } from "lucide-react";

import { getToken, setToken, type SourceConfig } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { LOCALES, Locale, useLocale, useT } from "@/lib/i18n";

const LINKS = [["/recipes", "Analysis library", "Analyses", BookOpen], ["/catalog", "Metric catalog", "Metrics", LayoutGrid], ["/methods", "Methods", "Methods", Workflow], ["/runs", "Runs", "Runs", History]] as const;

export function Nav() {
  const path = usePathname();
  const [token, setTok] = useState("");
  const [editing, setEditing] = useState(false);
  const { data: source, reload: reloadSource } = useApi<SourceConfig>("/sources/current");
  const t = useT();
  const { locale, setLocale } = useLocale();
  useEffect(() => setTok(getToken()), []);
  useEffect(() => {
    const syncSource = () => { setTok(getToken()); reloadSource(); };
    window.addEventListener("decision-layer.source-updated", syncSource);
    return () => window.removeEventListener("decision-layer.source-updated", syncSource);
  }, [reloadSource]);
  return <>
    <header className="app-topbar">
      <Link className="app-brand" href="/" aria-label="Decision Layer home"><span className="app-brand-mark"><Layers3 size={19} /></span><strong>Decision Layer</strong></Link>
      <span className="app-topbar-spacer" />
      {source?.auth_method !== "token" && source ? <Link className="app-credentials" href="/sources" title={t("Cube connection")}><Database size={15} />{t("Cube connection")}</Link> : source?.auth_method === "token" && editing ? (
        <form onSubmit={(e) => { e.preventDefault(); setToken(token); setEditing(false); location.reload(); }} className="app-token-form">
          <input type="password" aria-label={t("Cube user token")} placeholder={t("Cube user token")} value={token} onChange={(e) => setTok(e.target.value)} />
          <button type="submit">{t("Save")}</button>
        </form>
      ) : source?.auth_method === "token" ? <button className="app-credentials" onClick={() => setEditing(true)} title={token ? t("Using a token") : t("Cube user token required")}><ShieldCheck size={15} />{token ? t("Using a token") : t("Cube user token required")}</button> : null}
      <select className="app-locale" value={locale} onChange={(e) => setLocale(e.target.value as Locale)} aria-label="language">
        {LOCALES.map((l) => <option key={l} value={l}>{l}</option>)}
      </select>
    </header>
    <aside className="app-sidebar">
      <nav aria-label="Main navigation" className="app-nav-links">
        {LINKS.map(([href, label, mobileLabel, Icon]) => <Link key={href} href={href} className={path === href || path.startsWith(`${href}/`) ? "active" : ""} aria-current={path === href || path.startsWith(`${href}/`) ? "page" : undefined} aria-label={t(label)}><Icon size={17} /><span className="app-nav-label-full">{t(label)}</span><span className="app-nav-label-short">{t(mobileLabel)}</span></Link>)}
      </nav>
      <div className="app-sidebar-bottom"><Link href="/sources" className={path.startsWith("/sources") ? "active" : ""} aria-current={path.startsWith("/sources") ? "page" : undefined}><Database size={17} /><span>{t("Source settings")}</span></Link></div>
    </aside>
  </>;
}
