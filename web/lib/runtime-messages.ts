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
