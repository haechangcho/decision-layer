import type { MethodManifest } from "@/lib/api";
import styles from "./method-content.module.css";

export function PythonInputContract({ method }: { method: MethodManifest }) {
  const tables = Object.entries(method.data_inputs || {});
  if (!tables.length) return <p className={styles.muted}>
    고급 입력 연결을 사용하는 분석입니다. 소스의 집계 정의·기간 검사와 결과 구성을 어댑터가 처리합니다.
    일반 계산을 새로 작성할 때는 <code>python_method</code>와 <code>DataInput</code>으로 시작하세요.
  </p>;
  return <details className={styles.inputContract}>
    <summary>함수에 전달되는 데이터 · {tables.map(([name]) => name).join(", ")}</summary>
    <p>실행할 때 Cube 지표·차원과 기간을 연결합니다. 실행기가 조회와 입력 검사를 마친 뒤 함수에 데이터를 전달합니다.</p>
    {tables.map(([name, spec]) => <section key={name}>
      <h3><code>{name}</code> · {spec.format === "dataframe" ? "pandas DataFrame" : "행 목록"}</h3>
      <p>한 행: {spec.entity ? <><code>{spec.entity}</code>에 연결한 개체 하나</> : spec.dimensions.length ? <>{spec.dimensions.join(" × ")} 조합 하나</> : "전체 집계 한 건"}
        {spec.time_granularity && ` × ${spec.time_granularity} 기간 하나`} · 최소 {spec.minimum_rows}행</p>
      <div className={styles.contractScroll}><table><thead><tr><th>함수에서 읽는 컬럼</th><th>실행 시 연결</th></tr></thead><tbody>
        {spec.entity && <tr><td><code>unit</code></td><td>{spec.entity} · 공식 개체 키</td></tr>}
        {spec.time_granularity && <tr><td><code>time</code></td><td>선택한 시간 차원 · {spec.time_granularity}</td></tr>}
        {spec.dimensions.map(column => <tr key={column}><td><code>{column}</code></td><td>{column} · 차원</td></tr>)}
        {spec.measures.map(column => <tr key={column}><td><code>{column}</code></td><td>{column} · 지표</td></tr>)}
        {Object.entries(spec.columns || {}).map(([column, role]) => <tr key={column}><td><code>{role.multiple ? `${column}_0, ${column}_1, …` : column}</code></td>
          <td>{column} · {(role.accepted_kinds || [role.kind]).map(kind => kind === "measure" ? "지표" : "차원").join(" 또는 ")}{role.required ? " · 필수" : " · 선택"}</td></tr>)}
      </tbody></table></div>
      {!!spec.column_args?.length && <div>
        <h4>함수의 컬럼 인자</h4>
        <p>선택한 지표·차원을 조회한 뒤 실행기가 아래 인자를 채웁니다. 계산 옵션으로 직접 입력하지 않습니다.</p>
        <ul>{spec.column_args.map(argument => <li key={argument}><code>{argument}</code>{" ← "}
          <code>{spec.columns?.[argument]?.multiple ? `["${argument}_0", "${argument}_1", …]` : `"${argument}"`}</code>
          {spec.columns?.[argument]?.required === false && " (선택하지 않으면 빈 목록 또는 None)"}
        </li>)}</ul>
      </div>}
      <p>기간: {spec.period_parameter ? `${spec.period_parameter} 입력 (${spec.period_role})` : "Run에서 선택한 기간"}.
        필터: Run 범위{spec.filters_parameter && ` + ${spec.filters_parameter} 입력`}.</p>
    </section>)}
    <p className={styles.muted}>누락된 연결은 실행 전에 확인해야 합니다. 타입과 반환 데이터 검사는 사업적 의미·원천 데이터 완전성·인과관계를 보장하지 않습니다.</p>
  </details>;
}
