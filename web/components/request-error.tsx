"use client";

import { useState } from "react";
import { InspectorDialog } from "./inspector-dialog";
import { AlertCircle, RotateCw } from "lucide-react";
import { ApiError } from "@/lib/api";

export function RequestError({ title, error, retry }: { title: string; error: Error; retry: () => void }) {
  const [open, setOpen] = useState(false);
  const denied = error instanceof ApiError && [401, 403].includes(error.status);
  return <section className="request-error" role="alert">
    <AlertCircle size={21} />
    <div><strong>{title}</strong>
      <p>{denied ? "연결 설정에서 접근 권한을 확인해 주세요." : "서버가 실행 중인지 확인한 뒤 다시 시도해 주세요."}</p>
      <button type="button" className="ghost" onClick={() => setOpen(true)}>오류 상세</button><InspectorDialog title="오류 상세" open={open} onClose={() => setOpen(false)}><pre>{error.message}</pre></InspectorDialog>
    </div>
    <button className="ghost" onClick={retry}><RotateCw size={15} />다시 시도</button>
  </section>;
}
