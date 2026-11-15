import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  timeout: 180000,
  maxFailures: 1,
  expect: { timeout: 15000 },
  retries: 0,
  reporter: 'list',
  outputDir: '../../.artifacts/e2e-results',
  use: {
    baseURL: process.env.TEZKOR_E2E_BASE_URL || 'http://127.0.0.1:5174',
    headless: true,
    actionTimeout: 15000,
    navigationTimeout: 45000,
    launchOptions: { executablePath: process.env.TEZKOR_BROWSER_PATH || undefined },
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    { name: 'desktop', use: { viewport: { width: 1440, height: 1000 } } },
    { name: 'mobile', use: { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true } },
  ],
})
