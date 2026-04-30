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
    <div className="min-h-[calc(100vh-60px)] flex items-center justify-center px-4">
      <form
        onSubmit={submit}
        className="w-full max-w-sm bg-white border border-stone-200 rounded-xl shadow-sm p-6 space-y-4"
      >
        <div>
          <h2 className="text-xl font-semibold">
            {mode === "login" ? "Iniciar sesión" : "Crear cuenta"}
          </h2>
          <p className="text-sm text-stone-500 mt-1">
            Simulador Junta Banxico — uso interno del equipo.
          </p>
        </div>

        <label className="block">
          <span className="text-sm font-medium">Usuario</span>
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoCapitalize="none"
            autoCorrect="off"
            className="mt-1 w-full border border-stone-300 rounded-lg px-3 py-2"
            required
            minLength={3}
          />
        </label>

        {mode === "register" && (
          <label className="block">
            <span className="text-sm font-medium">Nombre para mostrar</span>
            <input
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              className="mt-1 w-full border border-stone-300 rounded-lg px-3 py-2"
              required
              minLength={1}
            />
          </label>
        )}

        <label className="block">
          <span className="text-sm font-medium">Contraseña</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 w-full border border-stone-300 rounded-lg px-3 py-2"
            required
            minLength={6}
          />
        </label>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <button
          type="submit"
          disabled={busy}
          className="w-full bg-banxico-600 hover:bg-banxico-700 disabled:opacity-50 text-white rounded-lg px-4 py-2"
        >
          {busy ? "…" : mode === "login" ? "Entrar" : "Crear cuenta"}
        </button>

        <button
          type="button"
          onClick={() => setMode(mode === "login" ? "register" : "login")}
          className="w-full text-sm text-stone-600 hover:underline"
        >
          {mode === "login" ? "¿Primera vez? Crear cuenta" : "Ya tengo cuenta — entrar"}
        </button>
      </form>
    </div>
  );
}
