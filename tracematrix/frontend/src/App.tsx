import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { Shell } from "./components/Shell";
import { getToken } from "./lib/api";
import { DashboardPage } from "./pages/DashboardPage";
import { ExplorerPage } from "./pages/ExplorerPage";
import { InvestigationNewPage } from "./pages/InvestigationNewPage";
import { LoginPage } from "./pages/LoginPage";
import { SourcesPage } from "./pages/SourcesPage";

const InvestigationPage = lazy(async () => ({
  default: (await import("./pages/InvestigationPage")).InvestigationPage,
}));

function RequireAuth({ children }: { children: React.ReactNode }) {
  if (!getToken()) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <RequireAuth>
            <Shell />
          </RequireAuth>
        }
      >
        <Route path="/" element={<DashboardPage />} />
        <Route path="/investigations/new" element={<InvestigationNewPage />} />
        <Route
          path="/investigations/:id"
          element={
            <Suspense fallback={<p className="text-sm text-slate-500">Loading case workspace…</p>}>
              <InvestigationPage />
            </Suspense>
          }
        />
        <Route path="/explorer" element={<ExplorerPage />} />
        <Route path="/sources" element={<SourcesPage />} />
      </Route>
    </Routes>
  );
}
