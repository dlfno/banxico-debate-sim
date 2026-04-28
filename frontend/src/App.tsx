import { Link, Route, Routes } from "react-router-dom";
import HomePage from "./pages/HomePage";
import ChatPage from "./pages/ChatPage";
import MeetingPage from "./pages/MeetingPage";

export default function App() {
  return (
    <div className="min-h-full flex flex-col">
      <header className="bg-banxico-700 text-white px-6 py-3 shadow-sm">
        <div className="max-w-6xl mx-auto flex items-center gap-6">
          <Link to="/" className="font-semibold tracking-wide">
            Simulador Junta Banxico
          </Link>
          <nav className="text-sm flex gap-4 opacity-90">
            <Link to="/" className="hover:underline">Inicio</Link>
            <Link to="/chat" className="hover:underline">Chat 1-a-1</Link>
            <Link to="/meeting" className="hover:underline">Junta</Link>
          </nav>
        </div>
      </header>
      <main className="flex-1">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/chat/:agentId" element={<ChatPage />} />
          <Route path="/meeting" element={<MeetingPage />} />
          <Route path="/meeting/:meetingId" element={<MeetingPage />} />
        </Routes>
      </main>
    </div>
  );
}
