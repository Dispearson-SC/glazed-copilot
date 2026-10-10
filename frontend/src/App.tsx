import { Navigate, Route, Routes } from "react-router-dom";
import CopilotPage from "./pages/CopilotPage";

/** The app is the Copiloto only: every other path lands on /copiloto. */
export default function App() {
  return (
    <Routes>
      <Route path="/copiloto" element={<CopilotPage />} />
      <Route path="*" element={<Navigate to="/copiloto" replace />} />
    </Routes>
  );
}
