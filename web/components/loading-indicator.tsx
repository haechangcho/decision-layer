"use client";

import { useT } from "@/lib/i18n";

export function LoadingIndicator() {
  return <svg className="dl-loading" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
    {Array.from({ length: 8 }, (_, index) => <rect key={index} x="10.5" y="0" width="3" height="7" rx="2" transform={`rotate(${45 * index} 12 12)`} style={{ animationDelay: `${0.15 * index}s` }} />)}
  </svg>;
}

export function LoadingState({ label }: { label?: string }) {
  const t = useT();
  return <div className="dl-loading-state" role="status" aria-live="polite"><LoadingIndicator /><span>{label ?? t("Loading…")}</span></div>;
}
