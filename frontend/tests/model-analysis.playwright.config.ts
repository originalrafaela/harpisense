import {defineConfig} from '@playwright/test';
export default defineConfig({
 testDir:'.',testMatch:'model-analysis.browser.ts',workers:1,
 use:{baseURL:'http://127.0.0.1:5491',headless:true},
 webServer:{command:'npm.cmd run dev -- --host 127.0.0.1 --port 5491 --strictPort',url:'http://127.0.0.1:5491/tests/model-analysis-preview.html',reuseExistingServer:true,timeout:30_000},
});
