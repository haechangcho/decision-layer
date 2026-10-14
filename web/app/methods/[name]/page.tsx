"use client";
import { MethodAvailability } from "@/components/method-availability";
import { LoadingState } from "@/components/loading-indicator";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Plus } from "lucide-react";
import { useApi } from "@/lib/hooks";
import type { MethodManifest } from "@/lib/api";
import { methodName } from "@/lib/method-name";
import styles from "../../library.module.css";
export default function MethodPage() {
  const { name } = useParams<{ name: string }>();
  const { data: method, error } = useApi<MethodManifest>(`/methods/${name}`);
  if (error) return <p role="alert">{error.message}</p>;
  if (!method) return <div className={styles.page}><LoadingState /></div>;
  return <div className={styles.page}>
    <Link className={styles.back} href="/methods"><ArrowLeft size={15} />분석 방법</Link>
    <div className={styles.heading}><div><h1>{(method.label || methodName(method.name))}</h1><p className={styles.methodId}>{method.name} · v{method.version}</p><p className={styles.intro}>{method.description}</p></div>
      <Link className={styles.primary} href={`/recipes/new?method=${encodeURIComponent(name)}`}><Plus size={16} />분석 절차 만들기</Link></div>
    <MethodAvailability key={name} name={decodeURIComponent(name)} />
    <section><h2 className={styles.panelTitle}>입력 조건</h2><dl className={styles.meta}>{Object.entries(method.roles).map(([key, role]) => <div className={styles.metaRow} key={key}><dt>{key}{role.required ? " · 필수" : ""}</dt><dd>{role.description || `${(role.accepted_kinds ?? [role.kind]).join(" / ")}${role.multiple ? "[]" : ""}`}</dd></div>)}</dl>
    <h2 className={styles.panelTitle}>분석 결과</h2><div className={styles.tags}>{method.outputs.map(output => <span className={styles.tag} key={output}>{output}</span>)}</div>
    <details><summary>파라미터 명세</summary><dl className={styles.meta}>{Object.entries(method.parameters).map(([key, parameter]) => <div className={styles.metaRow} key={key}><dt>{key}</dt><dd>{parameter.description || parameter.type}{parameter.default !== undefined && parameter.default !== null ? ` (${JSON.stringify(parameter.default)})` : ""}</dd></div>)}</dl></details></section>
  </div>;
}
