"use client";

import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { Artifact } from "@/lib/api";
import { populationLabel } from "@/lib/run-story";
import s from "./run-result-chart.module.css";

type Row = Record<string, unknown>;
const number = (value: unknown) => typeof value === "number" && Number.isFinite(value) ? value : null;
const label = (value: unknown) => typeof value === "string" ? value : String(value ?? "");
const compactNumber = (value: number) => new Intl.NumberFormat("ko-KR", { notation: "compact", maximumFractionDigits: 1 }).format(value);

export function RunResultChart({ artifact }: { artifact?: Artifact | null }) {
  if (!artifact || !artifact.data || typeof artifact.data !== "object") return null;
  const data = artifact.data as Record<string, unknown>;
  const rows = Array.isArray(data.rows) ? data.rows.filter((row): row is Row => !!row && typeof row === "object" && !Array.isArray(row)) : [];
  if (!rows.length) return null;

  if (artifact.type === "time_series" && typeof data.metric === "string") {
    const points = rows.flatMap((row) => number(row[data.metric as string]) === null ? [] : [{ name: label(row.period).slice(0, 10), value: number(row[data.metric as string])! }]);
    if (!points.length) return null;
    return <div className={s.chart} role="img" aria-label={`기간별 지표 값 그래프, ${points.length}개 기간`}>
      <ResponsiveContainer width="100%" height="100%">
        {points.length === 1 ? <BarChart data={points} margin={{ top: 14, right: 16, bottom: 4, left: 8 }}>
          <CartesianGrid vertical={false} stroke="var(--line)" /><XAxis dataKey="name" tickLine={false} axisLine={false} fontSize={11} /><YAxis tickFormatter={compactNumber} tickLine={false} axisLine={false} fontSize={11} width={64} />
          <Tooltip formatter={(value) => typeof value === "number" ? value.toLocaleString("ko-KR") : String(value)} /><Bar dataKey="value" name="지표 값" fill="var(--dl-data)" maxBarSize={110} radius={[3, 3, 0, 0]} isAnimationActive={false} />
        </BarChart> : <LineChart data={points} margin={{ top: 14, right: 16, bottom: 4, left: 8 }}>
          <CartesianGrid vertical={false} stroke="var(--line)" /><XAxis dataKey="name" tickLine={false} axisLine={false} fontSize={11} /><YAxis tickFormatter={compactNumber} tickLine={false} axisLine={false} fontSize={11} width={64} />
          <Tooltip formatter={(value) => typeof value === "number" ? value.toLocaleString("ko-KR") : String(value)} /><Line type="monotone" dataKey="value" name="지표 값" stroke="var(--dl-data)" strokeWidth={2.5} dot={{ r: 3 }} activeDot={{ r: 5 }} isAnimationActive={false} />
        </LineChart>}
      </ResponsiveContainer>
    </div>;
  }

  if (artifact.type === "breakdown_table") {
    const points = rows.slice(0, 8).flatMap((row, index) => number(row.metric) === null ? [] : [{ name: label(data.benchmark_aggregation === "semantic_provider" ? populationLabel(index, row.value) : row.value), value: number(row.metric)! }]);
    if (!points.length) return null;
    return <div className={s.chart} role="img" aria-label={`그룹별 지표 값 그래프, ${points.length}개 그룹`} style={{ height: Math.max(220, points.length * 40 + 42) }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={points} layout="vertical" margin={{ top: 4, right: 18, bottom: 4, left: 0 }}>
          <CartesianGrid horizontal={false} stroke="var(--line)" /><XAxis type="number" tickFormatter={compactNumber} tickLine={false} axisLine={false} fontSize={11} />
          <YAxis type="category" dataKey="name" width={110} tickLine={false} axisLine={false} fontSize={11} tick={{ fill: "var(--muted)" }} />
          <Tooltip formatter={(value) => typeof value === "number" ? value.toLocaleString("ko-KR") : String(value)} /><Bar dataKey="value" name="지표 값" fill="var(--dl-data)" maxBarSize={21} radius={[0, 3, 3, 0]} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </div>;
  }
  return null;
}
