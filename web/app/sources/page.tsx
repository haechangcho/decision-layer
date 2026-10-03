"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ArrowLeft, ArrowRight, Check, CheckCircle2, Database, Info, LockKeyhole, Save, ShieldCheck, Wifi } from "lucide-react";

import { api, getSourceAdminKey, getSourceCallerToken, setSourceAdminKey, setToken, type SourceConfig, type SourceReadiness, type SourceTestResult } from "@/lib/api";
import { LoadingIndicator } from "@/components/loading-indicator";
import { useT } from "@/lib/i18n";
import styles from "./sources.module.css";

const ENV_LABEL: Record<string, string> = {
  api_url: "CUBE_API_URL", auth_method: "CUBE_AUTH_METHOD", api_secret: "CUBE_API_SECRET", service_groups: "CUBE_SERVICE_GROUPS",
};

export default function SourcesPage() {
  const t = useT();
  const [source, setSource] = useState<SourceConfig | null>(null);
  const [adminKey, setAdminKey] = useState("");
  const [unlocked, setUnlocked] = useState(false);     // admin key accepted (shared deployment)
  const [url, setUrl] = useState("");
  const [auth, setAuth] = useState<"token" | "api_secret" | "none">("token");
  const [callerToken, setCallerToken] = useState("");
  const [secret, setSecret] = useState("");
  const [groups, setGroups] = useState("");
  const [test, setTest] = useState<SourceTestResult | null>(null);
  const [readiness, setReadiness] = useState<SourceReadiness | null>(null);
  const [busy, setBusy] = useState<"test" | "save" | "readiness" | "unlock" | null>(null);
  const [saved, setSaved] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const applyConfig = useCallback((config: SourceConfig) => {
    setSource(config);
    setUrl(config.api_url);
    setAuth(config.auth_method);
    setGroups(config.service_groups.join(", "));
  }, []);

  useEffect(() => {
    setAdminKey(getSourceAdminKey());
    setCallerToken(getSourceCallerToken());
    api<SourceConfig>("/sources/current")
      .then(applyConfig)
      .catch((cause) => setError(cause instanceof Error ? cause.message : t("Could not load the connection settings.")));
  }, [applyConfig, t]);

  // Fields a user may change: not fixed by an environment variable, and on a shared
  // deployment only after the admin key is accepted.
  const locked = (field: string) => !!source?.environment_overrides[field];
  const canEdit = !!source && source.editable && (!source.admin_required || unlocked);

  function normalizedGroups() { return groups.split(",").map((v) => v.trim()).filter(Boolean); }
  function editBody() {
    return { api_url: url, auth_method: auth, ...(auth === "api_secret" && secret ? { api_secret: secret } : {}), service_groups: normalizedGroups() };
  }

  async function unlock() {
    setBusy("unlock"); setError("");
    try {
      setSourceAdminKey(adminKey);
      applyConfig(await api<SourceConfig>("/sources/current", { admin: true }));
      setUnlocked(true);
    } catch (cause) {
      setUnlocked(false);
      setError(cause instanceof Error ? cause.message : t("Could not load the connection settings."));
    } finally { setBusy(null); }
  }

  async function testConnection() {
    setBusy("test"); setError(""); setMessage(""); setTest(null); setSaved(false); setReadiness(null);
    try {
      const result = await api<SourceTestResult>("/sources/current:test", {
        method: "POST", admin: source?.admin_required, callerToken: auth === "token" ? callerToken.trim() : "", body: editBody(),
      });
      setTest(result); setMessage(t("Cube connection verified. Save the settings to start exploring metrics."));
    } catch (cause) { setError(cause instanceof Error ? cause.message : t("Cube connection failed.")); }
    finally { setBusy(null); }
  }

  async function saveSettings() {
    setBusy("save"); setError(""); setMessage("");
    try {
      const config = await api<SourceConfig>("/sources/current", { method: "PUT", admin: source?.admin_required, body: editBody() });
      applyConfig(config); setSecret(""); setToken(auth === "token" ? callerToken.trim() : ""); window.dispatchEvent(new Event("decision-layer.source-updated")); setMessage(t("Connection settings saved.")); setSaved(true);
    } catch (cause) { setError(cause instanceof Error ? cause.message : t("Could not save the connection settings.")); }
    finally { setBusy(null); }
  }

  async function inspectReadiness() {
    setBusy("readiness"); setError(""); setReadiness(null);
    try { setReadiness(await api<SourceReadiness>("/sources/current/readiness", { callerToken: auth === "token" ? callerToken.trim() : "" })); }
    catch (cause) { setError(cause instanceof Error ? cause.message : t("Could not load readiness.")); }
    finally { setBusy(null); }
  }

  const envManaged = !!source && !source.editable;     // everything fixed by env vars → status only

  return <div className={styles.page}>
    <Link className={styles.back} href="/catalog"><ArrowLeft size={15} />{t("Metric catalog")}</Link>
    <div className={styles.heading}><span className={styles.icon}><Database size={21} /></span><div><h1>{t("Cube connection")}</h1><p>{t("Connects the Cube API address and access credentials.")}</p></div></div>

    {!source ? <p className={styles.help}>…</p> : <>
      {/* Current state summary — always shown */}
      <section className={styles.formSection}>
        <div className={styles.sectionHeading}><h2>{t("Current connection")}</h2>
          <span>{envManaged ? t("Managed by environment variables") : t("Saved on the server")}</span></div>
        <dl className={styles.summary}>
          <div><dt>{t("Cube API URL")}</dt><dd><code>{source.api_url}</code>{locked("api_url") && <small><LockKeyhole size={12} /> {ENV_LABEL.api_url}</small>}</dd></div>
          <div><dt>{t("Authentication")}</dt><dd>{source.auth_method}{locked("auth_method") && <small><LockKeyhole size={12} /> {ENV_LABEL.auth_method}</small>}</dd></div>
          <div><dt>{t("Service groups")}</dt><dd>{source.service_groups.join(", ") || "—"}{locked("service_groups") && <small><LockKeyhole size={12} /> {ENV_LABEL.service_groups}</small>}</dd></div>
        </dl>
        <div className={styles.actions}>
          <button className={styles.testButton} onClick={() => void testConnection()}
            disabled={busy !== null || (!envManaged && !canEdit) || (auth === "token" && !callerToken.trim() && !envManaged)}>
            {busy === "test" ? <><LoadingIndicator />{t("Testing…")}</> : <><Wifi size={16} />{t("Test connection")}</>}</button>
          {canEdit && <button className={styles.saveButton} onClick={() => void saveSettings()} disabled={busy !== null || !test || saved}>
            {busy === "save" ? t("Saving…") : <><Save size={15} />{t("Save settings")}</>}</button>}
        </div>
        {error && <div className={styles.alert} role="alert"><Info size={17} /><span>{error}</span></div>}
        {message && <div className={styles.success} role="status"><CheckCircle2 size={17} /><span>{message}</span></div>}
        {test && <div className={styles.testSummary}><CheckCircle2 size={17} />
          <div><strong>{t("Catalog access verified · {instance}", { instance: test.instance })}</strong>
            <small>{t("{measures} metrics · {dimensions} dimensions", { measures: test.measures, dimensions: test.dimensions + test.time_dimensions })}</small></div>
          <button onClick={() => void inspectReadiness()} disabled={busy !== null}>{t("Check readiness")}</button>
          <Link href="/catalog">{t("Explore metrics")} <ArrowRight size={14} /></Link></div>}
      </section>

      {/* Env-managed: nothing to edit here */}
      {envManaged && <p className={styles.help}><Info size={14} /> {t("This connection is managed by environment variables on the server. To change it, update the environment variables (.env) and restart.")}</p>}

      {/* Shared deployment, not yet unlocked: ask for the admin key */}
      {!envManaged && source.admin_required && !unlocked && <section className={styles.admin}>
        <span className={styles.adminIcon}><LockKeyhole size={20} /></span>
        <div className={styles.adminCopy}><h2>{t("Server administrator key")}</h2><p>{t("Changing the shared Cube connection on this deployment requires the server administrator key.")}</p></div>
        <form onSubmit={(e) => { e.preventDefault(); void unlock(); }} className={styles.adminForm}>
          <label htmlFor="admin-key">{t("Server administrator key")}</label>
          <input id="admin-key" type="password" autoComplete="current-password" disabled={busy !== null} value={adminKey} onChange={(e) => setAdminKey(e.target.value)} />
          <button type="submit" disabled={busy === "unlock" || !adminKey}>{busy === "unlock" ? t("Verifying…") : t("Open settings")}</button>
        </form>
        <p className={styles.help}>{t("The admin key is the DL_SOURCE_ADMIN_TOKEN set by the deployment administrator.")}</p>
      </section>}

      {/* Editable: the form */}
      {canEdit && <section className={styles.formSection}>
        <div className={styles.sectionHeading}><h2>{t("Connection settings")}</h2></div>
        <label className={styles.field}><span>{t("Cube API URL")}</span>
          <input value={url} onChange={(e) => { setUrl(e.target.value); setTest(null); setSaved(false); }} placeholder="https://cube.example.com/cubejs-api/v1" disabled={busy !== null || locked("api_url")} />
          {locked("api_url") && <small><LockKeyhole size={13} />{t("Fixed by environment variable")} · {ENV_LABEL.api_url}</small>}</label>
        <label className={styles.field}><span>{t("Authentication")}</span>
          <select value={auth} onChange={(e) => { setAuth(e.target.value as "token" | "api_secret" | "none"); setTest(null); setSaved(false); }} disabled={busy !== null || locked("auth_method")}>
            <option value="token">{t("Access token")}</option>
            {source.service_credentials_allowed && <><option value="api_secret">{t("API secret (development)")}</option><option value="none">{t("No authentication (development)")}</option></>}</select>
          {locked("auth_method") && <small><LockKeyhole size={13} />{t("Fixed by environment variable")} · {ENV_LABEL.auth_method}</small>}</label>
        {auth === "token" ? <label className={styles.field}><span>{t("Access token")}</span>
          <input type="password" autoComplete="off" value={callerToken} disabled={busy !== null} onChange={(e) => { setCallerToken(e.target.value); setTest(null); setSaved(false); }} placeholder={t("Enter without the Bearer prefix")} />
          <small>{t("Used only in this browser tab after saving. Not stored in the server database.")}</small></label>
        : auth === "api_secret" ? <>
          <label className={styles.field}><span>{t("Cube API secret")} {source.api_secret_configured ? t("(registered — enter to replace)") : ""}</span>
            <input type="password" autoComplete="new-password" value={secret} onChange={(e) => { setSecret(e.target.value); setTest(null); setSaved(false); }} placeholder={source.api_secret_configured ? t("Leave blank to keep the current value") : ""} disabled={busy !== null || locked("api_secret")} />
            {locked("api_secret") && <small><LockKeyhole size={13} />{t("Fixed by environment variable")} · {ENV_LABEL.api_secret}</small>}</label>
          <label className={styles.field}><span>{t("Service groups")}</span>
            <input value={groups} onChange={(e) => { setGroups(e.target.value); setTest(null); setSaved(false); }} disabled={busy !== null || locked("service_groups")} />
            <small>{t("Comma-separated. Use for development/local connections only.")}</small></label>
        </> : <p className={styles.help}>{t("Used only for development Cube with auth off. Every user shares the same data access.")}</p>}
      </section>}

      {readiness && <section className={styles.readiness}>
        <div className={styles.sectionHeading}><h2><ShieldCheck size={17} />{t("Metric readiness")}</h2><span>{t("{count} metrics", { count: readiness.metrics.length })}</span></div>
        {readiness.metrics.length === 0 ? <p>{t("No metrics are visible to the current user. Check the Cube model and access permissions.")}</p>
        : readiness.metrics.map((item) => <article className={styles.readinessRow} key={item.metric.ref}>
          <div><strong>{item.metric.title}</strong></div>
          <div>{([["Decomposition", item.checks.decomposition.status], ["Time", item.checks.time.status], ["Primary key", item.checks.entity_key.status]] as const).map(([label, state]) =>
            <span className={state === "missing" ? styles.warn : styles.ok} key={label}>{state === "missing" ? <Info size={13} /> : <Check size={13} />}{t(label)} · {state === "ready" ? t("available") : state === "not_applicable" ? t("not applicable") : t("needs attention")}</span>)}</div>
          {[item.checks.decomposition.impact, item.checks.time.impact, item.checks.entity_key.impact].filter(Boolean).length > 0 && <p>{[item.checks.decomposition.impact, item.checks.time.impact, item.checks.entity_key.impact].filter(Boolean).join(" ")}</p>}
        </article>)}</section>}
    </>}
  </div>;
}
