"use client";

import { useCallback } from "react";
import runtimeKorean from "../../src/decision_layer/i18n/ko.json";
import { type Locale, useLocale } from "./i18n";

// Share the server catalog: persisted system messages can be in the execution
// language. Translate known messages for display; never rewrite stored evidence
// or translate arbitrary agent/user prose.
const korean: Record<string, string> = runtimeKorean;
const original = new Map(Object.entries(korean).map(([id, text]) => [text, id]));

export function runtimeMessage(locale: Locale, message: string): string {
  const id = original.get(message) ?? message;
  return locale === "ko" ? korean[id] ?? message : id;
}

export function useRuntimeMessage() {
  const { locale } = useLocale();
  return useCallback((message: string) => runtimeMessage(locale, message), [locale]);
}

// Routine execution bookkeeping stays in the original Run record. Only these
// known system notices are omitted from the working view; unknown warnings stay.
const routineSkillNotices = new Set([
  "Returned rows are a bounded query result, not proof of complete population, appropriate peers or causal validity.",
  "Skill adherence, peer suitability, source completeness and causal assumptions are not verified. Only recorded query checks executed.",
  "Bound metrics, period, inherited population and provider query checks executed.",
  "Input checks do not establish source completeness, metric equivalence or causal identification.",
]);
export function isRoutineSkillNotice(message: string): boolean {
  return routineSkillNotices.has(runtimeMessage("en", message));
}
