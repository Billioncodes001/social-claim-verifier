import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "frontend/tests",
  fullyParallel: false,
  workers: 1,
  timeout: 45000,
  retries: process.env.CI ? 1 : 0,
  reporter: [
    ["list"],
    ["json", { outputFile: "artifacts/ui-regression.json" }],
  ],
  use: {
    baseURL: "http://127.0.0.1:8793",
    browserName: "chromium",
    channel: "chromium",
    viewport: { width: 1440, height: 1000 },
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  webServer: {
    command:
      (process.platform === "win32"
        ? '".venv\\Scripts\\python.exe"'
        : "python") + " scripts/ui_test_server.py",
    url: "http://127.0.0.1:8793/healthz",
    reuseExistingServer: false,
    timeout: 30000,
  },
});
