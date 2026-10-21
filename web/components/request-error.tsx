"use client";
import { useT } from "@/lib/i18n";

import { useState } from "react";
import { InspectorDialog } from "./inspector-dialog";
import { AlertCircle, RotateCw } from "lucide-react";
import { ApiError } from "@/lib/api";

export function RequestError({ title, error, retry }: { title: string; error: Error; retry: () => void }) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const denied = error instanceof ApiError && [401, 403].includes(error.status);
  return <section className="request-error" role="alert">
    <AlertCircle size={21} />
    <div><strong>{title}</strong>
      <p>{denied ? t("Check access permissions in connection settings.") : t("Check that the server is running, then try again.")}</p>
      <button type="button" className="ghost" onClick={() => setOpen(true)}>{t("Error details")}</button><InspectorDialog title={t("Error details")} open={open} onClose={() => setOpen(false)}><pre>{error.message}</pre></InspectorDialog>
    </div>
    <button className="ghost" onClick={retry}><RotateCw size={15} />{t("Retry")}</button>
  </section>;
}
