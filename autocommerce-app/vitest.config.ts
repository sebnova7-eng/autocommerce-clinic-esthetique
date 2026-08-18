import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(process.cwd(), "client", "src"),
      "@shared": path.resolve(process.cwd(), "shared"),
      "@assets": path.resolve(process.cwd(), "attached_assets"),
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./client/src/test/setup.ts"],
    exclude: ["node_modules/**", "dist/**", "coverage/**", "e2e/**"],
    coverage: {
      provider: "v8",
      reporter: ["text", "json-summary", "html"],
      include: ["client/src/**/*.{ts,tsx}"],
      exclude: [
        "client/src/**/*.d.ts",
        "client/src/main.tsx",
        "client/src/test/**",
        "client/src/__tests__/**",
      ],
      reportOnFailure: true,
    },
  },
});
