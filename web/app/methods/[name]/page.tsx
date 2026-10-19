"use client";
import { MethodAssetEditor } from "@/features/method-asset-editor";
import { MethodMarkdown } from "@/components/method-content";
import { MethodAvailability } from "@/components/method-availability";
import { PythonInputContract } from "@/components/python-input-contract";
import { LoadingState } from "@/components/loading-indicator";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Plus } from "lucide-react";
import { useApi } from "@/lib/hooks";
import type { MethodManifest, MethodGuide } from "@/lib/api";
import { methodName } from "@/lib/method-name";
import styles from "../../library.module.css";
export default function MethodPage() {
  const { name } = useParams<{ name: string }>();
  const { data: method, error, reload } = useApi<MethodManifest>(`/methods/${name}`);
  if (error && !method) return <p role="alert">{error.message}</p>;
  if (!method) return <div className={styles.page}><LoadingState /></div>;
  return <div className={styles.page}>
    {error && <p role="alert">분석 정보를 갱신하지 못했습니다. 작성 중인 내용은 유지됩니다. {error.message}</p>}
    <Link className={styles.back} href="/methods"><ArrowLeft size={15} />분석 방법</Link>
    <div className={styles.heading}><div><h1>{(method.label || methodName(method.name))}</h1><p className={styles.methodId}>{method.name} · v{method.version}</p><p className={styles.intro}>{method.description}</p></div>
      {(method.implementation !== "skill" || method.agent_executable) && <Link className={styles.primary} href={`/recipes/new?method=${encodeURIComponent(name)}`}><Plus size={16} />분석 절차 만들기</Link>}</div>
    {method.implementation === "skill" ? <MethodAssetEditor key={`editor:${name}`} name={name} onPublished={reload}><SkillGuide key={method.version} name={name} executable={!!method.agent_executable} /></MethodAssetEditor> : <>
    <MethodAvailability key={`availability:${name}`} name={decodeURIComponent(name)} />
    <MethodAssetEditor key={`editor:${name}`} name={name} onPublished={reload} />
    <PythonInputContract method={method} />
    <section aria-label="Method 테스트">
      <h2 className={styles.panelTitle}>실제 데이터로 테스트</h2>
      <p>입력 지표·차원과 기간을 선택하고 ‘결과 확인’을 실행하세요. 절차를 저장하기 전에 결과·검사·실제 조회를 확인할 수 있습니다. 코드를 수정했다면 게시된 버전으로 실행됩니다.</p>
      <Link className={styles.primary} href={`/recipes/new?method=${encodeURIComponent(name)}`}>입력 선택하고 테스트</Link>
    </section>
    <section><h2 className={styles.panelTitle}>입력 조건</h2><dl className={styles.meta}>{Object.entries(method.roles).map(([key, role]) => <div className={styles.metaRow} key={key}><dt>{key}{role.required ? " · 필수" : ""}</dt><dd>{role.description || `${(role.accepted_kinds ?? [role.kind]).join(" / ")}${role.multiple ? "[]" : ""}`}</dd></div>)}</dl>
    <h2 className={styles.panelTitle}>분석 결과</h2><div className={styles.tags}>{method.outputs.map(output => <span className={styles.tag} key={output}>{output}</span>)}</div>
    <details><summary>파라미터 명세</summary><dl className={styles.meta}>{Object.entries(method.parameters).map(([key, parameter]) => <div className={styles.metaRow} key={key}><dt>{key}</dt><dd>{parameter.description || parameter.type}{parameter.default !== undefined && parameter.default !== null ? ` (${JSON.stringify(parameter.default)})` : ""}</dd></div>)}</dl></details></section></>}
  </div>;
}

function SkillGuide({ name, executable }: { name: string; executable: boolean }) {
  const { data: guide, error } = useApi<MethodGuide>(`/methods/${name}/guide`);
  if (error) return <p role="alert">{error.message}</p>;
  if (!guide) return <LoadingState />;
  return <section aria-label="Skill 지침">
    <h2>AI가 참고하는 분석 지침</h2>
    <p>{executable ? "Recipe의 분석 단계로 사용할 수 있습니다. Claude·Codex가 지침에 따라 Cube 쿼리를 실행하며, 각 요청과 결과가 이 단계에 기록됩니다. Web에서 시작하면 AI 실행을 기다립니다." : "Claude·Codex에서 이 지침을 참고해 등록된 도구를 실행합니다."}</p>
    <p>지침 자체는 실행 검사나 분석 결과가 아닙니다. 고정된 실행 순서가 필요하면 Recipe를 사용하세요.</p>
    <MethodMarkdown content={guide.markdown} />
    <h3>사용하는 실행 도구</h3><ul>{guide.suggested_methods.map(tool => <li key={tool}><Link href={`/methods/${encodeURIComponent(tool)}`}>{tool}</Link></li>)}</ul>
    <details><summary>버전과 내용 해시</summary><code>v{guide.version} · {guide.sha256}</code></details>
  </section>;
}
