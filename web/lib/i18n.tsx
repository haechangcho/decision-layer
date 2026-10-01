"use client";

// UI text is English in code; other languages map the English text to a translation.
// The first render is always English (matches the server render); the stored or browser
// language is applied after mount. API calls send the same language as Accept-Language.

import { createContext, useCallback, useContext, useEffect, useState } from "react";

export type Locale = "en" | "ko";
export const LOCALES: Locale[] = ["en", "ko"];
const KEY = "decision-layer.locale";

const ko: Record<string, string> = {
  // Sources / connection
  "Metric catalog": "지표 탐색",
  "Cube connection": "Cube 연결",
  "Connects the Cube API address and access credentials.": "Cube API 주소와 접근 자격 증명을 연결합니다.",
  "Current connection": "현재 연결",
  "Connected": "정상 연결됨",
  "Connection settings": "연결 설정",
  "Managed by environment variables": "환경변수로 관리 중",
  "Saved on the server": "서버에 저장됨",
  "Cube API URL": "Cube API URL",
  "Authentication": "인증 방식",
  "Access token": "Access token",
  "API secret (development)": "API secret (개발용)",
  "No authentication (development)": "인증 없음 (개발용)",
  "Enter without the Bearer prefix": "Bearer 접두사 없이 입력",
  "Used only in this browser tab after saving. Not stored in the server database.": "저장 후 이 브라우저 탭에서만 사용합니다. 서버 DB에는 저장하지 않습니다.",
  "Fixed by environment variable": "환경변수로 고정됨",
  "Cube API secret": "Cube API secret",
  "(registered — enter to replace)": "(등록됨, 입력 시 교체)",
  "Leave blank to keep the current value": "비워 두면 기존 값 유지",
  "Service groups": "서비스 그룹",
  "Comma-separated. Use for development/local connections only.": "쉼표로 구분합니다. 개발·로컬 연결에만 사용하세요.",
  "Test connection": "연결 테스트",
  "Testing…": "연결 확인 중…",
  "Save settings": "설정 저장",
  "Saving…": "저장 중…",
  "Cube connection verified. Save the settings to start exploring metrics.": "Cube 연결을 확인했습니다. 설정 저장 후 지표를 탐색할 수 있어요.",
  "Connection settings saved.": "연결 설정을 저장했습니다.",
  "Catalog access verified · {instance}": "카탈로그 접근 확인됨 · {instance}",
  "{measures} metrics · {dimensions} dimensions": "{measures}개 지표 · {dimensions}개 차원",
  "Check readiness": "준비 상태 확인",
  "Explore metrics": "지표 탐색",
  "Metric readiness": "지표 준비 상태",
  "{count} metrics": "{count}개 지표",
  "No metrics are visible to the current user. Check the Cube model and access permissions.": "현재 사용자에게 공개된 측정값이 없습니다. Cube 모델과 접근 권한을 확인해 주세요.",
  "Decomposition": "분해",
  "Time": "시간",
  "Primary key": "기본 키",
  "available": "가능",
  "not applicable": "해당 없음",
  "needs attention": "확인 필요",
  "This connection is managed by environment variables on the server. To change it, update the environment variables (.env) and restart.": "이 연결은 서버의 환경변수로 관리됩니다. 바꾸려면 환경변수(.env)를 수정하고 서버를 재시작하세요.",
  "Server administrator key": "서버 관리자 키",
  "Changing the shared Cube connection on this deployment requires the server administrator key.": "이 배포에서 공유 Cube 연결을 바꾸려면 서버 관리자 키가 필요합니다.",
  "Open settings": "설정 열기",
  "Verifying…": "확인 중…",
  "The admin key is the DL_SOURCE_ADMIN_TOKEN set by the deployment administrator.": "관리 키는 배포 관리자가 설정한 DL_SOURCE_ADMIN_TOKEN입니다.",
  "Could not load the connection settings.": "연결 설정을 불러오지 못했습니다.",
  "Cube connection failed.": "Cube 연결에 실패했습니다.",
  "Could not save the connection settings.": "연결 설정을 저장하지 못했습니다.",
  "Could not load readiness.": "준비 상태를 불러오지 못했습니다.",
  "Used only for development Cube with auth off. Every user shares the same data access.": "인증이 꺼진 개발용 Cube에만 사용합니다. 모든 사용자가 같은 데이터 접근 권한을 갖습니다.",
  "Computing… {s}s ({run})": "계산 중… {s}초 ({run})",
  "Running…": "실행 중…",
  "Run": "실행",
  "The result will appear here.": "결과가 여기에 표시됩니다.",
  "Registered analysis Methods. Input forms are generated from each Method's manifest (roles and parameters).":
    "등록된 분석 Method. 입력 화면은 각 Method의 manifest(역할·파라미터)로 만들어집니다.",
  "Roles": "역할",
  "Not connected": "연결 안 됨",
  "Catalog (what this caller can see)": "Catalog (이 사용자에게 보이는 것)",
  "Search (ref, title, description)": "검색 (ref, 제목, 설명)",
  "All": "전체",
  "Title": "제목",
  "Description": "설명",
  "Metric scope": "지표 범위",
  "Primary metric": "주 지표",
  "Related metrics": "관련 지표",
  "Preferred dimensions": "우선 차원",
  "Limits": "한도",
  "steps {steps} · queries {queries}": "단계 {steps} · 쿼리 {queries}",
  "Validators": "검증",
  "Steps": "단계",
  "Allowed methods": "허용 Method",
  "Guidance": "진행 안내",
  "Question (for the record)": "질문 (기록용)",
  "Start investigation": "조사 시작",
  "The organisation's analysis procedures, kept as YAML files and read from DL_RECIPES_DIR.":
    "조직이 정한 분석 절차. 파일(YAML)로 관리되며 DL_RECIPES_DIR에서 읽습니다.",
  "No recipes are registered.": "등록된 Recipe가 없습니다.",
  "Question": "질문",
  "None (single Method run)": "없음 (Method 단독 실행)",
  "Scope": "범위",
  "Run by": "실행자",
  "Usage": "사용량",
  "steps {steps}/{maxSteps} · queries {queries}/{maxQueries}": "단계 {steps}/{maxSteps} · 쿼리 {queries}/{maxQueries}",
  "Conclusion": "결론",
  "Sharing": "공유",
  "Read-only (owner {owner})": "읽기 전용 (소유자 {owner})",
  "Computing: {what} (started {time})": "계산 중: {what} (시작 {time})",
  "Last job error [{code}] {message}": "마지막 실행 오류 [{code}] {message}",
  "No step has run yet.": "아직 실행한 단계가 없습니다.",
  "User identifiers, comma separated (* = everyone)": "사용자 식별자, 쉼표로 구분 (* = 모두)",
  "Save": "저장",
  "It won't open for recipients who lack access to its metrics": "받는 사람에게 권한이 없는 지표가 있으면 열리지 않습니다",
  "Next step": "다음 단계",
  "Run step": "단계 실행",
  "Conclusion (when closing)": "결론 (닫을 때)",
  "Close investigation": "조사 닫기",
  "Refresh": "새로고침",
  "Your runs (recipe runs and single Method runs). Use them to reopen or share a result.":
    "내 실행 기록(Recipe 실행과 Method 단독 실행). 같은 결과를 다시 열거나 공유할 때 씁니다.",
  "Started": "시작",
  "Status": "상태",
  "optional": "선택",
  "Remove": "삭제",
  "+ Add": "+ 추가",
  "required": "필수",
  "default {value}": "기본값 {value}",
  "(default)": "(기본값)",
  "Analysis scope": "분석 범위",
  "Period": "기간",
  "Date basis": "날짜 기준",
  "(optional — only when asked)": "(선택 — 물어올 때만)",
  "Shared filters": "공통 필터",
  "Roles (semantic refs)": "역할 (semantic ref)",
  "Parameters": "파라미터",
  "Cube user token": "Cube 사용자 토큰",
  "Cube user token required": "Cube 토큰 필요",
  "Using a token": "토큰 사용 중",
  "Service credentials": "서비스 자격 증명",
  "Interpretation: {level}": "해석 수준: {level}",
  "Put one of these values into the {field} parameter and run again.": "위 값 중 하나를 해당 파라미터({field})에 넣어 다시 실행하세요.",
  "Show {n} executed queries": "실행한 쿼리 {n}개 보기",
  "Hide {n} executed queries": "실행한 쿼리 {n}개 숨기기",
};

const CATALOGS: Record<Locale, Record<string, string>> = { en: {}, ko };

export function storedLocale(): Locale {
  try {
    const saved = (localStorage.getItem(KEY) ?? localStorage.getItem("analytica.locale")) as Locale | null;
    if (saved && LOCALES.includes(saved)) return saved;
  } catch { /* storage unavailable */ }
  if (typeof navigator !== "undefined" && navigator.language.toLowerCase().startsWith("ko")) return "ko";
  return "en";
}

export function translate(locale: Locale, msg: string, values?: Record<string, string | number>): string {
  const template = CATALOGS[locale][msg] ?? msg;
  return values ? template.replace(/\{(\w+)\}/g, (m, k) => (k in values ? String(values[k]) : m)) : template;
}

type Ctx = { locale: Locale; setLocale: (l: Locale) => void };
const LocaleContext = createContext<Ctx>({ locale: "en", setLocale: () => {} });

export function LocaleProvider({ children }: { children: React.ReactNode }) {
  const [locale, set] = useState<Locale>("en");
  useEffect(() => set(storedLocale()), []);
  const setLocale = useCallback((l: Locale) => {
    try { localStorage.setItem(KEY, l); } catch { /* storage unavailable */ }
    set(l);
  }, []);
  return <LocaleContext.Provider value={{ locale, setLocale }}>{children}</LocaleContext.Provider>;
}

export function useLocale() {
  return useContext(LocaleContext);
}

export function useT() {
  const { locale } = useContext(LocaleContext);
  return useCallback((msg: string, values?: Record<string, string | number>) => translate(locale, msg, values), [locale]);
}
