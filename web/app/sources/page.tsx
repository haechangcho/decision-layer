"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ArrowLeft, ArrowRight, Check, CheckCircle2, Database, Info, LockKeyhole, Save, ShieldCheck, Wifi } from "lucide-react";

import { api, getSourceAdminKey, getSourceCallerToken, setSourceAdminKey, setToken, type SourceConfig, type SourceReadiness, type SourceTestResult } from "@/lib/api";
import { LoadingIndicator } from "@/components/loading-indicator";
import { useT } from "@/lib/i18n";
import styles from "./sources.module.css";

const PROVIDER_TITLES = { cube: "Cube", dbt: "dbt Semantic Layer" };

export default function SourcesPage() {
  const t = useT();
  const [source, setSource] = useState<SourceConfig | null>(null);
  const [providers, setProviders] = useState<SourceConfig[]>([]);
  const [provider, setProvider] = useState<SourceConfig["provider"]>("cube");
  const prefix = { cube: "CUBE", dbt: "DBT" }[provider];
  const ENV_LABEL = { api_url: `${prefix}_API_URL`, auth_method: `${prefix}_AUTH_METHOD`, api_secret: "CUBE_API_SECRET", service_groups: "CUBE_SERVICE_GROUPS" };
  const [instance, setInstance] = useState("");
  const [environmentId, setEnvironmentId] = useState("");
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

  function invalidateTest() { setTest(null); setSaved(false); setReadiness(null); setMessage(""); setError(""); }

  const applyConfig = useCallback((config: SourceConfig) => {
    setSource(config);
    setProvider(config.provider);
    setInstance(config.instance);
    setEnvironmentId(config.environment_id ? String(config.environment_id) : "");
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
    api<SourceConfig[]>("/sources/providers").then(setProviders).catch(() => {});
  }, [applyConfig, t]);

  // Fields a user may change: not fixed by an environment variable, and on a shared
  // deployment only after the admin key is accepted.
  const selectedConfig = provider === source?.provider ? source : providers.find(p => p.provider === provider);
  const locked = (field: string) => !!selectedConfig?.environment_overrides[field];
  const canEdit = !!source && source.editable && (!source.admin_required || unlocked);

  function normalizedGroups() { return groups.split(",").map((v) => v.trim()).filter(Boolean); }
  function editBody() {
    return { provider, instance, api_url: url, auth_method: auth, ...(provider === "dbt" ? { environment_id: Number(environmentId) } : {}), ...(auth === "api_secret" && secret ? { api_secret: secret } : {}), service_groups: normalizedGroups() };
  }

  function chooseProvider(name: SourceConfig["provider"]) {
    const config = providers.find(p => p.provider === name);
    setProvider(name); setSecret(""); setCallerToken(""); setTest(null); setSaved(false); setReadiness(null); setMessage(""); setError("");
    setUrl(config?.api_url || ""); setInstance(config?.instance || "local");
    setEnvironmentId(config?.environment_id ? String(config.environment_id) : "");
    setAuth(config?.auth_method || "token"); setGroups(config?.service_groups.join(", ") || "");
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
      if (envManaged && auth === "token") setToken(callerToken.trim());
      setTest(result);
    } catch (cause) { setError(cause instanceof Error ? cause.message : t("Connection failed.")); }
    finally { setBusy(null); }
  }

  async function saveSettings() {
    setBusy("save"); setError(""); setMessage("");
    try {
      const config = await api<SourceConfig>("/sources/current", { method: "PUT", admin: source?.admin_required, body: editBody() });
      applyConfig(config); setProviders(previous => [...previous.filter(item => item.provider !== config.provider), config]); setSecret(""); setToken(auth === "token" ? callerToken.trim() : ""); window.dispatchEvent(new Event("decision-layer.source-updated")); setMessage(t("Connection settings saved.")); setSaved(true);
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
  const matchesSaved = !!source && source.provider === provider && source.api_url === url && source.instance === instance && source.auth_method === auth && JSON.stringify(source.service_groups) === JSON.stringify(normalizedGroups()) && !secret && (auth !== "token" || callerToken.trim() === getSourceCallerToken()) && (provider !== "dbt" || source.environment_id === Number(environmentId));

  return <div className={styles.page}>
    <Link className={styles.back} href="/catalog"><ArrowLeft size={15} />{t("Metric catalog")}</Link>
    <div className={styles.heading}><span className={styles.icon}><Database size={21} /></span><div><h1>{t("Semantic layer connection")}</h1><p>{t("Connect your governed metrics and dimensions.")}</p></div></div>

    {!source ? error ? <div className={styles.alert} role="alert"><Info size={17} /><div>{error}<button onClick={() => { setError(""); void api<SourceConfig>("/sources/current").then(applyConfig).catch(cause => setError(String(cause))); }}>{t("Retry")}</button></div></div> : <div className={styles.skeleton} aria-label={t("Loading…")}><LoadingIndicator /><div /><div /><div /></div> : <>
      {/* Current state summary — always shown */}
      {!canEdit && <section className={styles.formSection}>
        <div className={styles.sectionHeading}><h2>{t("Current connection")}</h2>
          <span>{envManaged ? t("Managed by environment variables") : t("Saved on the server")}</span></div>
        <dl className={styles.summary}>
          <div><dt>{t("Provider")}</dt><dd>{t(PROVIDER_TITLES[source.provider])}</dd></div>
          <div><dt>{t("API URL")}</dt><dd><code>{source.api_url}</code>{locked("api_url") && <small><LockKeyhole size={12} />{ENV_LABEL.api_url}</small>}</dd></div>
          {source.provider === "dbt" && <div><dt>{t("Environment ID")}</dt><dd>{source.environment_id || "—"}</dd></div>}
          <div><dt>{t("Authentication")}</dt><dd>{t(source.auth_method === "none" ? "No authentication (development)" : source.auth_method === "api_secret" ? "API secret (development)" : "Access token")}{source.environment_overrides.auth_method && <small><LockKeyhole size={12} /> {source.provider === "cube" ? "CUBE_AUTH_METHOD" : "DBT_AUTH_METHOD"}</small>}</dd></div>
          {source.provider === "cube" && source.auth_method === "api_secret" && <div><dt>{t("Service groups")}</dt><dd>{source.service_groups.join(", ") || "—"}{locked("service_groups") && <small><LockKeyhole size={12} /> {ENV_LABEL.service_groups}</small>}</dd></div>}
        </dl>
      </section>}

      {/* Env-managed: nothing to edit here */}
      {envManaged && <p className={styles.help}><Info size={14} /> {t("This connection is managed by environment variables on the server. To change it, update the environment variables (.env) and restart.")}</p>}
      {envManaged && auth === "token" && <label className={styles.field}><span id="readonly-token-label">{t("Access token")}</span><input aria-labelledby="readonly-token-label" type="password" autoComplete="off" value={callerToken} disabled={busy !== null} onChange={e => { setCallerToken(e.target.value); invalidateTest(); }} placeholder={t("Enter without the Bearer prefix")} /><small>{t("Used only in this browser tab after saving. Not stored in the server database.")}</small></label>}

      {/* Shared deployment, not yet unlocked: ask for the admin key */}
      {!envManaged && source.admin_required && !unlocked && <section className={styles.admin}>
        <span className={styles.adminIcon}><LockKeyhole size={20} /></span>
        <div className={styles.adminCopy}><h2>{t("Server administrator key")}</h2><p>{t("Changing the shared connection requires the server administrator key.")}</p></div>
        <form onSubmit={(e) => { e.preventDefault(); void unlock(); }} className={styles.adminForm}>
          <label htmlFor="admin-key">{t("Server administrator key")}</label>
          <input id="admin-key" type="password" autoComplete="current-password" disabled={busy !== null} value={adminKey} onChange={(e) => setAdminKey(e.target.value)} />
          <button type="submit" disabled={busy === "unlock" || !adminKey}>{busy === "unlock" ? t("Verifying…") : t("Open settings")}</button>
        </form>
        <p className={styles.help}>{t("The admin key is the DL_SOURCE_ADMIN_TOKEN set by the deployment administrator.")}</p>
      </section>}

      {/* Editable: the form */}
      {canEdit && <section className={styles.formSection}>
        <div className={styles.sectionHeading}><h2>{t("Connection settings")}</h2><span>{!matchesSaved ? t("Unsaved changes") : t("Saved on the server")}</span></div>
        <label className={styles.field}><span>{t("Provider")}</span><select value={provider} onChange={e => chooseProvider(e.target.value as SourceConfig["provider"])} disabled={busy !== null || locked("provider")}><option value="cube">Cube</option><option value="dbt">dbt Semantic Layer</option></select></label>
        {provider === "dbt" && <p className={styles.help}>{t("Connect to your organization's dbt Semantic Layer using its GraphQL endpoint, deployment environment ID and access token.")}</p>}
        <label className={styles.field}><span id="source-url-label">{t("API URL")}</span>
          <input aria-labelledby="source-url-label" aria-describedby="source-url-help" value={url} onChange={(e) => { setUrl(e.target.value); invalidateTest(); }} placeholder={provider === "cube" ? "https://cube.example.com/cubejs-api/v1" : "https://semantic-layer.cloud.getdbt.com/api/graphql"} disabled={busy !== null || locked("api_url")} />
          <small id="source-url-help">{t("Use an address reachable from the Decision Layer server.")}</small>
          {locked("api_url") && <small><LockKeyhole size={13} />{t("Fixed by environment variable")} · {ENV_LABEL.api_url}</small>}</label>
        {provider === "dbt" && <label className={styles.field}><span id="dbt-environment-label">{t("Environment ID")}</span>
          <input aria-labelledby="dbt-environment-label" inputMode="numeric" value={environmentId} onChange={e => { setEnvironmentId(e.target.value); invalidateTest(); }} placeholder="123456" disabled={busy !== null || locked("environment_id")} />
          <small>{t("Use the deployment environment configured for Semantic Layer in dbt.")}</small></label>}
        <label className={styles.field}><span id="source-auth-label">{t("Authentication")}</span>
          <select aria-labelledby="source-auth-label" value={auth} onChange={(e) => { setAuth(e.target.value as "token" | "api_secret" | "none"); invalidateTest(); }} disabled={busy !== null || locked("auth_method")}>
            <option value="token">{t("Access token")}</option>
            {source.service_credentials_allowed && provider !== "dbt" && <>{provider === "cube" && <option value="api_secret">{t("API secret (development)")}</option>}<option value="none">{t("No authentication (development)")}</option></>}</select>
          {locked("auth_method") && <small><LockKeyhole size={13} />{t("Fixed by environment variable")} · {ENV_LABEL.auth_method}</small>}</label>
        {auth === "token" ? <label className={styles.field}><span id="source-token-label">{t("Access token")}</span>
          <input aria-labelledby="source-token-label" aria-describedby="source-token-help" type="password" autoComplete="off" value={callerToken} disabled={busy !== null} onChange={(e) => { setCallerToken(e.target.value); invalidateTest(); }} placeholder={t("Enter without the Bearer prefix")} />
          <small id="source-token-help">{t("Used only in this browser tab after saving. Not stored in the server database.")}</small></label>
        : auth === "api_secret" ? locked("api_secret") ? <p className={styles.credential}><LockKeyhole size={14} />{t("API secret is configured on the server.")}</p> : <label className={styles.field}><span>{t("Cube API secret")}</span>
            <input type="password" autoComplete="new-password" value={secret} onChange={(e) => { setSecret(e.target.value); invalidateTest(); }} placeholder={selectedConfig?.api_secret_configured ? t("Leave blank to keep the current value") : ""} disabled={busy !== null} />
          </label> : <p className={styles.help}>{t("Local development only. Every user shares the same data access.")}</p>}
        <details className={styles.advanced}><summary>{t("Additional connection settings")}</summary>
          <label className={styles.field}><span>{t("Instance")}</span><input value={instance} onChange={e => { setInstance(e.target.value); invalidateTest(); }} disabled={busy !== null || locked("instance")} /><small>{t("Identifies this connection in saved semantic references.")}{locked("instance") && ` · ${prefix}_INSTANCE`}</small></label>
          {auth === "api_secret" && <label className={styles.field}><span>{t("Service groups")}</span><input value={groups} onChange={e => { setGroups(e.target.value); invalidateTest(); }} disabled={busy !== null || locked("service_groups")} /><small>{t("Comma-separated. Use for development/local connections only.")}</small></label>}
        </details>
      </section>}

      <section className={styles.connectionActions} aria-label={t("Connection verification")}>
        {canEdit && !test && <p className={styles.actionHint}>{t("Test the connection before saving. Then explore the available metrics.")}</p>}
        <div className={styles.actions}>
          <button className={styles.testButton} onClick={() => void testConnection()}
            disabled={busy !== null || (!envManaged && !canEdit) || !/^https?:\/\/\S+$/.test(url) || (auth === "token" && !callerToken.trim()) || (provider === "dbt" && !/^[1-9]\d*$/.test(environmentId))}>
            {busy === "test" ? <><LoadingIndicator />{t("Testing…")}</> : <><Wifi size={16} />{t("Test connection")}</>}</button>
          {canEdit && <button className={styles.saveButton} onClick={() => void saveSettings()} disabled={busy !== null || !test || saved}>
            {busy === "save" ? t("Saving…") : <><Save size={15} />{t("Save settings")}</>}</button>}
        </div>
        {error && <div className={styles.alert} role="alert"><Info size={17} /><span>{error}</span></div>}
        {message && <div className={styles.success} role="status"><CheckCircle2 size={17} /><span>{message}</span></div>}
        {test && <div className={styles.testSummary}><CheckCircle2 size={17} />
          <div><strong>{t("Catalog access verified · {instance}", { instance: test.instance })}</strong>
            <small>{t("{measures} metrics · {dimensions} dimensions", { measures: test.measures, dimensions: test.dimensions + test.time_dimensions })}</small>{canEdit && !saved && !matchesSaved && <small>{t("Save this connection to use its metrics.")}</small>}</div>
          <button onClick={() => void inspectReadiness()} disabled={busy !== null || (!saved && !matchesSaved)}>{t("Check readiness")}</button>
          {(saved || matchesSaved) && <Link href="/catalog">{t("Explore metrics")} <ArrowRight size={14} /></Link>}</div>}
      </section>

      {readiness && <section className={styles.readiness}>
        <div className={styles.sectionHeading}><h2><ShieldCheck size={17} />{t("Metric readiness")}</h2><span>{t("{count} metrics", { count: readiness.metrics.length })}</span></div>
        {readiness.metrics.length === 0 ? <p>{t("No metrics are visible. Check the semantic models and access permissions.")}</p>
        : readiness.metrics.map((item) => <article className={styles.readinessRow} key={item.metric.ref}>
          <div><strong>{item.metric.title}</strong></div>
          <div>{([["Decomposition", item.checks.decomposition.status], ["Time", item.checks.time.status], ["Primary key", item.checks.entity_key.status]] as const).map(([label, state]) =>
            <span className={state === "missing" ? styles.warn : styles.ok} key={label}>{state === "missing" ? <Info size={13} /> : <Check size={13} />}{t(label)} · {state === "ready" ? t("available") : state === "not_applicable" ? t("not applicable") : t("needs attention")}</span>)}</div>
          {[item.checks.decomposition.impact, item.checks.time.impact, item.checks.entity_key.impact].filter(Boolean).length > 0 && <p>{[item.checks.decomposition.impact, item.checks.time.impact, item.checks.entity_key.impact].filter(Boolean).join(" ")}</p>}
        </article>)}</section>}
    </>}
  </div>;
}
