import { Link, Navigate, NavLink, Route, Routes, useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { AuthProvider, useAuth } from "./auth";
import { api } from "./api";
import type { VersionInfo } from "./types";
import HomePage from "./pages/HomePage";
import ChatPage from "./pages/ChatPage";
import MeetingPage from "./pages/MeetingPage";
import LoginPage from "./pages/LoginPage";
import AgentsPage from "./pages/AgentsPage";
import WorldMapPage from "./pages/WorldMapPage";

function formatRelative(date: Date): string {
  const diffMs = Date.now() - date.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return "ahora mismo";
  if (diffMin < 60) return `hace ${diffMin} min`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `hace ${diffHr} h`;
  const diffDay = Math.floor(diffHr / 24);
  if (diffDay < 30) return `hace ${diffDay} d`;
  const diffMonth = Math.floor(diffDay / 30);
  return `hace ${diffMonth} mes${diffMonth > 1 ? "es" : ""}`;
}

function VersionBadge({ info }: { info: VersionInfo }) {
  const buildTime =
    info.build_time && info.build_time !== "unknown"
      ? new Date(info.build_time)
      : null;
  const sha =
    info.git_commit && info.git_commit !== "unknown"
      ? info.git_commit.substring(0, 7)
      : null;
  if (!buildTime && !sha) return null;

  const tooltipLines = [
    sha ? `Commit: ${info.git_commit}` : null,
    info.git_commit_date && info.git_commit_date !== "unknown"
      ? `Commit fecha: ${info.git_commit_date}`
      : null,
    buildTime ? `Desplegada: ${buildTime.toLocaleString()}` : null,
    info.process_started_at
      ? `Proceso iniciado: ${new Date(info.process_started_at).toLocaleString()}`
      : null,
  ].filter(Boolean);

  return (
    <div
      className="flex items-center gap-1.5 opacity-70 hover:opacity-100 transition cursor-help"
      title={tooltipLines.join("\n")}
    >
      <span className="w-1.5 h-1.5 rounded-full bg-accent-500"></span>
      {sha && <span className="font-mono">v{sha}</span>}
      {buildTime && (
        <>
          {sha && <span className="opacity-50">·</span>}
          <span>desplegada {formatRelative(buildTime)}</span>
        </>
      )}
    </div>
  );
}

function BanxicoLogo() {
  return (
    <Link to="/" className="flex items-center gap-3 group">
      <div className="flex items-center justify-center w-11 h-11 rounded-sm bg-white text-banxico-800 font-serif font-bold text-xl shadow-sm border border-white/20">
        B
      </div>
      <div className="leading-tight">
        <div className="text-[10px] uppercase tracking-[0.22em] text-white/70 font-medium">
          Banco de México
        </div>
        <div className="font-serif text-xl font-semibold text-white group-hover:text-accent-100 transition">
          Simulador Junta de Gobierno
        </div>
      </div>
    </Link>
  );
}

function UtilityBar() {
  const { user, logout } = useAuth();
  return (
    <div className="bg-banxico-900 text-white/80 text-xs">
      <div className="max-w-7xl mx-auto px-6 py-1.5 flex items-center gap-5">
        <span className="hidden md:inline opacity-70">
          Sistema interno de simulación · Uso académico
        </span>
        <div className="ml-auto flex items-center gap-4">
          <a
            href="https://www.banxico.org.mx"
            target="_blank"
            rel="noreferrer"
            className="hover:text-white transition"
          >
            Banxico.org.mx
          </a>
          {user && (
            <>
              <span className="opacity-40">|</span>
              <span className="text-white/90">
                <span className="opacity-60 mr-1">Sesión:</span>
                {user.display_name}
              </span>
              <button
                onClick={logout}
                className="px-2 py-0.5 rounded-sm border border-white/20 hover:bg-white/10 hover:border-white/40 transition"
              >
                Cerrar sesión
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function MainBanner() {
  return (
    <div className="relative bg-gradient-to-r from-banxico-800 via-banxico-700 to-banxico-800 border-b-4 border-accent-600">
      {/* textura sutil tipo arquitectura */}
      <div
        aria-hidden
        className="absolute inset-0 opacity-[0.07] pointer-events-none"
        style={{
          backgroundImage:
            "radial-gradient(circle at 20% 50%, white 0.5px, transparent 1px), radial-gradient(circle at 80% 50%, white 0.5px, transparent 1px)",
          backgroundSize: "32px 32px",
        }}
      />
      <div className="relative max-w-7xl mx-auto px-6 py-5 flex items-center">
        <BanxicoLogo />
      </div>
    </div>
  );
}

function MainNav() {
  const { user } = useAuth();
  if (!user) return null;
  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `relative px-4 py-3 text-sm font-semibold tracking-wide uppercase transition ${
      isActive
        ? "text-banxico-700 bg-white"
        : "text-white hover:bg-banxico-600/40"
    }`;
  return (
    <nav className="bg-banxico-700 border-b border-banxico-800/40">
      <div className="max-w-7xl mx-auto px-6 flex items-stretch gap-0 overflow-x-auto">
        <NavLink to="/" end className={linkClass}>
          Inicio
        </NavLink>
        <NavLink to="/agentes" className={linkClass}>
          Agentes
        </NavLink>
        <NavLink to="/chat" className={linkClass}>
          Chat 1-a-1
        </NavLink>
        <NavLink to="/meeting" className={linkClass}>
          Junta
        </NavLink>
        <NavLink to="/mapa" className={linkClass}>
          Mapa Mundial
        </NavLink>
      </div>
    </nav>
  );
}

function Footer() {
  const version = useQuery({
    queryKey: ["version"],
    queryFn: api.getVersion,
    staleTime: 1000 * 60 * 30, // 30 min
  });
  return (
    <footer className="bg-banxico-900 text-white/70 text-xs mt-auto">
      <div className="max-w-7xl mx-auto px-6 py-5 flex flex-col md:flex-row items-center gap-3 md:gap-6">
        <div className="font-serif text-white">
          Simulador Junta de Gobierno · Banco de México
        </div>
        <div className="opacity-60">
          Proyecto académico — no constituye comunicación oficial de Banxico.
        </div>
        {version.data && <VersionBadge info={version.data} />}
        <div className="md:ml-auto opacity-60">
          © {new Date().getFullYear()}
        </div>
      </div>
    </footer>
  );
}

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) {
    return <p className="p-6 text-stone-500">Cargando…</p>;
  }
  if (!user) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }
  return <>{children}</>;
}

function AppRoutes() {
  const { user } = useAuth();
  return (
    <Routes>
      <Route
        path="/login"
        element={user ? <Navigate to="/" replace /> : <LoginPage />}
      />
      <Route
        path="/"
        element={
          <RequireAuth>
            <HomePage />
          </RequireAuth>
        }
      />
      <Route
        path="/agentes"
        element={
          <RequireAuth>
            <AgentsPage />
          </RequireAuth>
        }
      />
      <Route
        path="/mapa"
        element={
          <RequireAuth>
            <WorldMapPage />
          </RequireAuth>
        }
      />
      <Route
        path="/chat"
        element={
          <RequireAuth>
            <ChatPage />
          </RequireAuth>
        }
      />
      <Route
        path="/chat/:agentId"
        element={
          <RequireAuth>
            <ChatPage />
          </RequireAuth>
        }
      />
      <Route
        path="/chat/session/:sessionId"
        element={
          <RequireAuth>
            <ChatPage />
          </RequireAuth>
        }
      />
      <Route
        path="/meeting"
        element={
          <RequireAuth>
            <MeetingPage />
          </RequireAuth>
        }
      />
      <Route
        path="/meeting/:meetingId"
        element={
          <RequireAuth>
            <MeetingPage />
          </RequireAuth>
        }
      />
    </Routes>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <div className="min-h-full flex flex-col bg-sand-50">
        <UtilityBar />
        <MainBanner />
        <MainNav />
        <main className="flex-1">
          <AppRoutes />
        </main>
        <Footer />
      </div>
    </AuthProvider>
  );
}
