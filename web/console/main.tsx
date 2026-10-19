import { createRoot } from "react-dom/client";
import { BrowserRouter, Routes, Route, Navigate, Link } from "react-router-dom";
import { SSRProvider } from "@fluentui/react-components";
import { Nav } from "@/components/nav";
import { LocaleProvider } from "@/lib/i18n";
import { useApi } from "@/lib/hooks";
import Methods from "@/app/methods/page";
import Method from "@/app/methods/[name]/page";
import Recipes from "@/app/recipes/page";
import Recipe from "@/app/recipes/[name]/page";
import RecipeEdit from "@/app/recipes/[name]/edit/page";
import Runs from "@/app/runs/page";
import Run from "@/app/runs/[id]/page";
import Sources from "@/app/sources/page";
import Catalog from "@/app/catalog/page";
import "@/app/globals.css";

function ProjectContext() {
  const { data } = useApi<{ name: string; path: string }>("/project");
  return data ? <div role="status" style={{ padding: "8px 24px", borderBottom: "1px solid #ddd" }}>프로젝트: <strong>{data.name}</strong> · 로컬 실행 · <Link to="/sources">데이터 연결 설정</Link><details><summary>프로젝트 위치</summary>{data.path}<p>프로젝트 Method는 파일에서 수정하고 이 화면에서 테스트합니다. 등록 검사는 실제 분석 실행과 다릅니다.</p></details></div> : null;
}
function App() {
  return <SSRProvider><LocaleProvider><BrowserRouter basename="/ui"><div className="app-shell"><Nav /><main className="app-main"><ProjectContext /><Routes>
    <Route path="/" element={<Navigate to="/methods" replace />} />
    <Route path="/methods" element={<Methods />} /><Route path="/methods/:name" element={<Method />} />
    <Route path="/recipes" element={<Recipes />} /><Route path="/recipes/:name/edit" element={<RecipeEdit />} /><Route path="/recipes/:name" element={<Recipe />} />
    <Route path="/runs" element={<Runs />} /><Route path="/runs/:id" element={<Run />} />
    <Route path="/sources" element={<Sources />} /><Route path="/catalog" element={<Catalog />} />
    <Route path="*" element={<p>페이지를 찾을 수 없습니다.</p>} />
  </Routes></main></div></BrowserRouter></LocaleProvider></SSRProvider>;
}
createRoot(document.getElementById("root")!).render(<App />);
