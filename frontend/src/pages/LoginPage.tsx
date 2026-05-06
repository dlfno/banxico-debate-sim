import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth";

export default function LoginPage() {
  const navigate = useNavigate();
  const { login, register } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (mode === "login") {
        await login(username.trim(), password);
      } else {
        await register(username.trim(), displayName.trim(), password);
      }
      navigate("/", { replace: true });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-[calc(100vh-200px)] flex items-center justify-center px-4 py-10">
      <form
        onSubmit={submit}
        className="w-full max-w-md institutional-card overflow-hidden"
      >
        <div className="bg-banxico-700 text-white px-6 py-5 border-b-4 border-accent-600">
          <div className="text-[10px] uppercase tracking-[0.22em] text-white/70 font-medium">
            Acceso institucional
          </div>
          <h2 className="font-serif text-2xl">
            {mode === "login" ? "Iniciar sesión" : "Crear cuenta"}
          </h2>
          <p className="text-sm text-white/70 mt-1">
            Simulador Junta Banxico — uso académico interno.
          </p>
        </div>

        <div className="p-6 space-y-4 bg-white">
          <label className="block">
            <span className="text-xs font-semibold uppercase tracking-wider text-banxico-700">
              Usuario
            </span>
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoCapitalize="none"
              autoCorrect="off"
              className="input-institutional mt-1"
              required
              minLength={3}
            />
          </label>

          {mode === "register" && (
            <label className="block">
              <span className="text-xs font-semibold uppercase tracking-wider text-banxico-700">
                Nombre para mostrar
              </span>
              <input
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                className="input-institutional mt-1"
                required
                minLength={1}
              />
            </label>
          )}

          <label className="block">
            <span className="text-xs font-semibold uppercase tracking-wider text-banxico-700">
              Contraseña
            </span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="input-institutional mt-1"
              required
              minLength={6}
            />
          </label>

          {error && (
            <p className="text-sm text-red-700 bg-red-50 border border-red-200 rounded px-3 py-2">
              {error}
            </p>
          )}

          <button type="submit" disabled={busy} className="btn-primary w-full">
            {busy ? "…" : mode === "login" ? "Entrar" : "Crear cuenta"}
          </button>

          <button
            type="button"
            onClick={() => setMode(mode === "login" ? "register" : "login")}
            className="w-full text-sm text-accent-700 hover:text-accent-600 hover:underline pt-2 border-t border-sand-200"
          >
            {mode === "login" ? "¿Primera vez? Crear cuenta" : "Ya tengo cuenta — entrar"}
          </button>
        </div>
      </form>
    </div>
  );
}
