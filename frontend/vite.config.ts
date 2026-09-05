import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The dev server proxies /api/* to the FastAPI backend so there are no CORS
// issues and the frontend needs no backend changes. Start the API with:
//   python -m uvicorn api.app:app --reload --port 8000
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
