import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Relative asset URLs (base "./"): the backend rewrites <base href> in
// index.html to BASE_PATH at runtime, so one build works at the site root
// or under a proxy prefix like /finance.
export default defineConfig({
  base: "./",
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
  build: {
    outDir: "dist",
  },
});
