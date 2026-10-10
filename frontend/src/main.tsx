import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { registerSW } from "virtual:pwa-register";
import { SessionProvider } from "./SessionContext";
import { AuthGate } from "./AuthContext";
import App from "./App";
import "./index.css";

registerSW({ immediate: true });

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <AuthGate>
        <SessionProvider>
          <App />
        </SessionProvider>
      </AuthGate>
    </BrowserRouter>
  </StrictMode>,
);
