"use client";

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
  const [view, setView] = useState("overview");
  const { name } = useParams<{ name: string }>();
  const { data: method, error, reload } = useApi<MethodManifest>(`/methods/${name}`);
  const skill = method?.implementation === "skill";
  return <div className={styles.page}>
    <Link className={styles.back} href="/methods"><ArrowLeft size={15} />분석 방법</Link>
    {error && <RequestError title="분석 방법을 불러오지 못했습니다" error={error} retry={reload} />}
    {!method ? !error && <LoadingState /> : <>
      <div className={styles.heading}><div>
        <p className={styles.eyebrow}>{skill ? "SKILL" : "PYTHON"}</p>
        <h1>{methodTitle(method)}</h1>
        <p className={styles.methodId}>{method.name} / v{method.version}</p>
        <p className={styles.intro}>{method.description}</p>
      </div></div>
      <WorkspaceTabs id="method" label="Method 정보" value={view} onChange={setView} items={[
        {value:"overview",label:"개요와 입력"}, {value:"implementation",label:skill ? "분석 지침" : "Python 코드"}, {value:"executions",label:"실행 기록"}
      ]} />
      <div id="method-panel-overview" role="tabpanel" aria-labelledby="method-tab-overview" hidden={view !== "overview"}>
      {(!skill || method.agent_executable) && <section className={styles.methodPanel} aria-label="Method 테스트">
        <h2>{skill ? "AI와 실행하기" : "실제 데이터로 테스트"}</h2>
        <p>{skill ? "MCP로 연결한 AI에게 이 방법으로 분석을 요청하세요. AI가 실행한 쿼리와 응답을 기록합니다." : "지표와 기간을 선택해 실행한 뒤, 결과와 검사 내용을 확인하세요. 테스트는 실행 기록에 남습니다."}</p>
        <Link className={styles.primary} href={`/recipes/new?method=${encodeURIComponent(name)}`}>{skill ? "분석 절차 만들기" : "입력 선택하고 테스트"}</Link>
        {skill && <p>웹에서 절차를 시작하면 연결된 AI의 실행을 기다립니다.</p>}
      </section>}
      {!skill && <section className={styles.methodPanel}>
        <h2>입력 조건</h2>
        {!Object.keys(method.data_inputs ?? {}).length && <dl className={styles.meta}>{Object.entries(method.roles).map(([key, role]) => <div className={styles.metaRow} key={key}>
          <dt>{role.label || key}{role.required ? " *" : ""}</dt><dd>{role.description || (role.accepted_kinds ?? [role.kind]).join(" / ")}{role.multiple ? " (여러 개 선택)" : ""}</dd>
        </div>)}</dl>}
        <MethodAvailability key={`availability:${name}`} name={decodeURIComponent(name)} />
        <PythonInputContract method={method} />
        {!!Object.keys(method.parameters).length && <section className={styles.methodOptions}><h3>계산 옵션</h3><div><dl className={styles.meta}>
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
  const { data: guide, error, reload } = useApi<MethodGuide>(`/methods/${name}/guide`);
  if (error) return <RequestError title="지침을 불러오지 못했습니다" error={error} retry={reload} />;
  if (!guide) return <LoadingState />;
  return <section aria-label="Skill 지침">
    <h2>AI가 참고하는 분석 지침</h2>
    <MethodMarkdown content={guide.markdown} />
    {!!guide.suggested_methods.length && <><h3>사용하는 실행 도구</h3><ul>{guide.suggested_methods.map(tool => <li key={tool}><Link href={`/methods/${encodeURIComponent(tool)}`}>{tool}</Link></li>)}</ul></>}
    <p className={styles.contentHash}>v{guide.version} / SHA-256 {guide.sha256}</p>
  </section>;
}
