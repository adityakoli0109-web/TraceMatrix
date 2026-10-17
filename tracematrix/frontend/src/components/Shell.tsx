import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { setToken } from "../lib/api";

const links = [
  { to: "/", label: "Dashboard" },
  { to: "/investigations/new", label: "New case" },
  { to: "/explorer", label: "Explorer" },
  { to: "/sources", label: "OSINT sources" },
];

export function Shell() {
  const navigate = useNavigate();
  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[250px_minmax(0,1fr)]">
      <aside className="flex flex-col border-b border-line bg-[#101b2d] text-white lg:min-h-screen lg:border-b-0">
        <div className="flex items-center gap-3 px-6 py-6">
          <div className="grid h-10 w-10 place-items-center rounded-xl bg-[#244fc4] text-sm font-bold tracking-tight shadow-lg shadow-blue-950/30">
            TM
          </div>
          <div>
            <div className="text-[16px] font-semibold tracking-tight">TraceMatrix</div>
            <div className="mt-0.5 text-[11px] text-slate-400">On-chain intelligence</div>
          </div>
        </div>
        <div className="px-6 pb-2 pt-4 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">Workspace</div>
        <nav className="flex gap-1 overflow-x-auto px-3 pb-4 lg:flex-col lg:overflow-visible">
          {links.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.to === "/"}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-xl px-3.5 py-3 text-[13px] font-medium ${
                  isActive
                    ? "bg-[#1e2c43] text-white shadow-inner"
                    : "text-slate-400 hover:bg-[#19263a] hover:text-white"
                }`
              }
            >
              <span aria-hidden="true" className={`h-1.5 w-1.5 rounded-full ${link.to === "/" ? "bg-sky-400" : "bg-current opacity-60"}`} />
              {link.label}
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto hidden px-5 pb-6 lg:block">
          <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
            <div className="flex items-center gap-2 text-xs font-semibold text-slate-200">
              <span className="h-2 w-2 rounded-full bg-emerald-400" />
              Analyst workspace
            </div>
            <p className="mt-2 text-[11px] leading-5 text-slate-400">Evidence-led triage. Connections are leads to review, never proof of identity.</p>
          </div>
        </div>
      </aside>
      <div className="flex min-w-0 flex-col">
        <header className="sticky top-0 z-10 flex items-center justify-between border-b border-slate-200/80 bg-white/85 px-5 py-3 backdrop-blur-xl sm:px-8">
          <div>
            <div className="text-[11px] font-medium uppercase tracking-[0.14em] text-slate-400">Investigation workspace</div>
            <div className="mt-0.5 text-[13px] font-semibold text-slate-700">Public-evidence analysis</div>
          </div>
          <button
            className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-600 hover:border-slate-300 hover:bg-slate-50"
            onClick={() => {
              setToken(null);
              navigate("/login");
            }}
          >
            Sign out
          </button>
        </header>
        <main className="mx-auto w-full max-w-[1500px] flex-1 p-5 sm:p-8">
          <Outlet />
        </main>
        <footer className="border-t border-slate-200/80 px-5 py-3 text-center text-[11px] text-slate-400 sm:px-8">
          TraceMatrix · Research leads require independent verification
        </footer>
      </div>
    </div>
  );
}
