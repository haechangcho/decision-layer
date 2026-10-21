"use client";
import { useT } from "@/lib/i18n";

import { useState } from "react";
import { WorkspaceTabs } from "@/components/workspace-tabs";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { MethodAssetEditor } from "@/features/methods/method-asset-editor";
import { MethodMarkdown } from "@/features/methods/method-content";
import { MethodAvailability } from "@/components/method-availability";
import { PythonInputContract } from "@/features/methods/python-input-contract";
import { MethodExecutions } from "@/features/methods/method-executions";
import { LoadingState } from "@/components/loading-indicator";
import { RequestError } from "@/components/request-error";
import { useApi } from "@/lib/hooks";
import type { MethodManifest, MethodGuide } from "@/lib/api";
import { methodTitle } from "@/lib/method-name";
import styles from "../../library.module.css";

export default function MethodPage() {
  const t = useT();
  const [view, setView] = useState("overview");
  const { name } = useParams<{ name: string }>();
  const { data: method, error, reload } = useApi<MethodManifest>(`/methods/${name}`);
  const skill = method?.implementation === "skill";
  return <div className={styles.page}>
    <Link className={styles.back} href="/methods"><ArrowLeft size={15} />{t("Methods")}</Link>
    {error && <RequestError title={t("Could not load the Method")} error={error} retry={reload} />}
    {!method ? !error && <LoadingState /> : <>
      <div className={styles.heading}><div>
        <p className={styles.eyebrow}>{skill ? "SKILL" : "PYTHON"}</p>
        <h1>{methodTitle(method, t)}</h1>
        <p className={styles.methodId}>{method.name} / v{method.version}</p>
        <p className={styles.intro}>{method.description}</p>
      </div></div>
      <WorkspaceTabs id="method" label={t("Method information")} value={view} onChange={setView} items={[
        {value:"overview",label:t("Overview and inputs")}, {value:"implementation",label:skill ? t("Analysis instructions") : t("Python code")}, {value:"executions",label:t("Runs")}
      ]} />
      <div id="method-panel-overview" role="tabpanel" aria-labelledby="method-tab-overview" hidden={view !== "overview"}>
      {(!skill || method.agent_executable) && <section className={styles.methodPanel} aria-label={t("Test Method")}>
        <h2>{skill ? t("Run with AI") : t("Test with real data")}</h2>
        <p>{skill ? t("Ask your connected AI to use this Method. Its queries and responses are recorded.") : t("Choose metrics and dates, then inspect results and checks. Tests are saved as Runs.")}</p>
        <Link className={styles.primary} href={`/recipes/new?method=${encodeURIComponent(name)}`}>{skill ? t("Create analysis procedure") : t("Choose inputs and test")}</Link>
        {skill && <p>{t("Starting this procedure waits for the connected AI to execute it.")}</p>}
      </section>}
      {!skill && <section className={styles.methodPanel}>
        <h2>{t("Inputs")}</h2>
        {!Object.keys(method.data_inputs ?? {}).length && <dl className={styles.meta}>{Object.entries(method.roles).map(([key, role]) => <div className={styles.metaRow} key={key}>
          <dt>{role.label || key}{role.required ? " *" : ""}</dt><dd>{role.description || (role.accepted_kinds ?? [role.kind]).join(" / ")}{role.multiple ? t("(select multiple)") : ""}</dd>
        </div>)}</dl>}
        <MethodAvailability key={`availability:${name}`} name={decodeURIComponent(name)} />
        <PythonInputContract method={method} />
        {!!Object.keys(method.parameters).length && <section className={styles.methodOptions}><h3>{t("Calculation options")}</h3><div><dl className={styles.meta}>
          {Object.entries(method.parameters).map(([key, parameter]) => <div className={styles.metaRow} key={key}><dt>{parameter.label || key}</dt><dd>{parameter.description || parameter.type}{parameter.default != null ? ` (${JSON.stringify(parameter.default)})` : ""}</dd></div>)}
        </dl></div></section>}
      </section>}
      </div>
      <div id="method-panel-implementation" role="tabpanel" aria-labelledby="method-tab-implementation" hidden={view !== "implementation"}>
        <MethodAssetEditor key={`editor:${name}`} name={name} onPublished={reload}>{skill ? <SkillGuide key={method.version} name={name} /> : undefined}</MethodAssetEditor>
      </div>
      <div id="method-panel-executions" role="tabpanel" aria-labelledby="method-tab-executions" hidden={view !== "executions"}>
        <MethodExecutions key={`${name}:${method.version}`} method={method} />
      </div>
    </>}
  </div>;
}

function SkillGuide({ name }: { name: string }) {
  const t = useT();
  const { data: guide, error, reload } = useApi<MethodGuide>(`/methods/${name}/guide`);
  if (error) return <RequestError title={t("Could not load the instructions")} error={error} retry={reload} />;
  if (!guide) return <LoadingState />;
  return <section aria-label={t("Skill instructions")}>
    <h2>{t("Analysis instructions for AI")}</h2>
    <MethodMarkdown content={guide.markdown} />
    {!!guide.suggested_methods.length && <><h3>{t("Execution tools")}</h3><ul>{guide.suggested_methods.map(tool => <li key={tool}><Link href={`/methods/${encodeURIComponent(tool)}`}>{tool}</Link></li>)}</ul></>}
    <p className={styles.contentHash}>v{guide.version} / SHA-256 {guide.sha256}</p>
  </section>;
}
