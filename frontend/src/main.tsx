import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import App from "./App";
import { ApiError } from "./api/client";
import "./styles.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // La app habla con un servidor en la propia red: reintentar tres veces
      // solo retrasa el mensaje de error. Un reintento basta para un corte
      // momentáneo de WiFi.
      retry: (count, error) => !(error instanceof ApiError) && count < 1,
      refetchOnWindowFocus: true,
      staleTime: 30_000,
    },
    mutations: { retry: false },
  },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);

// Service worker: cachea el armazón para que la app abra sin red. Los datos
// siguen viniendo del servidor; esto no es modo offline completo (D6).
if ("serviceWorker" in navigator && import.meta.env.PROD) {
  window.addEventListener("load", () => {
    void navigator.serviceWorker.register("/sw.js");
  });
}
