import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    // En desarrollo la UI corre en su propio puerto; en produccion se sirve
    // desde el mismo proceso que la API, asi que el codigo siempre llama a
    // rutas relativas `/api/...` y no necesita saber donde esta el backend.
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: true },
    },
    host: true, // accesible desde el movil en la red local
  },
  build: {
    outDir: "dist",
    sourcemap: true,
  },
});
