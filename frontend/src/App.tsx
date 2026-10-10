import { Navigate, Route, Routes } from "react-router-dom";
import ChatPage from "./pages/ChatPage";
import HomePage from "./pages/HomePage";
import LoginPage from "./pages/LoginPage";
import BottomNav from "./shell/BottomNav";
import TopBar from "./shell/TopBar";

export default function App() {
  return (
    <div className="app min-h-screen bg-surface text-on-surface">
      <TopBar />
      <main className="pt-20 pb-24 px-margin max-w-3xl mx-auto flex flex-col gap-space-md">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
      <BottomNav />
    </div>
  );
}
