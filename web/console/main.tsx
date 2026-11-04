import { useT } from "@/lib/i18n";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { SSRProvider } from "@fluentui/react-components";
import { Nav } from "@/components/nav";
import { LocaleProvider } from "@/lib/i18n";
import { ProjectMenu } from "@/components/project-menu";
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

function NotFound() {
  const t = useT();
  return <p>{t("Page not found.")}</p>;
}

function App() {
  return <SSRProvider><LocaleProvider><BrowserRouter basename="/ui"><div className="app-shell"><Nav context={<ProjectMenu />} /><main id="main-content" className="app-main"><Routes>
    <Route path="/" element={<Navigate to="/recipes" replace />} />
    <Route path="/methods" element={<Methods />} /><Route path="/methods/:name" element={<Method />} />
    <Route path="/recipes" element={<Recipes />} /><Route path="/recipes/:name/edit" element={<RecipeEdit />} /><Route path="/recipes/:name" element={<Recipe />} />
    <Route path="/runs" element={<Runs />} /><Route path="/runs/:id" element={<Run />} />
    <Route path="/sources" element={<Sources />} /><Route path="/catalog" element={<Catalog />} />
    <Route path="*" element={<NotFound />} />
  </Routes></main></div></BrowserRouter></LocaleProvider></SSRProvider>;
}
createRoot(document.getElementById("root")!).render(<App />);
