"use client";

import styles from "./workspace-tabs.module.css";

export function WorkspaceTabs({ id, label, items, value, onChange }: {
  id: string; label: string; items: { value: string; label: string }[]; value: string; onChange: (value: string) => void;
}) {
  return <div className={styles.tabs} role="tablist" aria-label={label} onKeyDown={event => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const buttons = [...event.currentTarget.querySelectorAll<HTMLButtonElement>("[role=tab]")];
    const current = buttons.indexOf(document.activeElement as HTMLButtonElement);
    const next = event.key === "Home" ? 0 : event.key === "End" ? buttons.length - 1 : (current + (event.key === "ArrowRight" ? 1 : -1) + buttons.length) % buttons.length;
    buttons[next]?.focus(); buttons[next]?.click();
  }}>{items.map(item => <button key={item.value} type="button" id={`${id}-tab-${item.value}`} role="tab"
    aria-selected={value === item.value} aria-controls={`${id}-panel-${item.value}`} tabIndex={value === item.value ? 0 : -1}
    onClick={() => onChange(item.value)}>{item.label}</button>)}</div>;
}
