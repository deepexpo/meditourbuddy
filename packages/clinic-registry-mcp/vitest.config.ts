import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    globalSetup: "./test/global-setup.ts",
    testTimeout: 15000,
    hookTimeout: 30000,
  },
});
