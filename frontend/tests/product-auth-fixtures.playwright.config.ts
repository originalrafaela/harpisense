import {defineConfig} from '@playwright/test';

const baseURL='http://127.0.0.1:52177';
process.env.HARPISENSE_TEST_URL=baseURL;
// Isolated sink only: browser specs must never contact a developer's backend.
process.env.HARPI_API_TUNNEL_TARGET='http://127.0.0.1:9';

export default defineConfig({
 testDir:'.',
 testMatch:['tests/config-manager.spec.ts','tests/operational-review.spec.ts','tests/cases-v2-ui.spec.ts'],
 workers:1,
 reporter:'list',
 outputDir:'test-results/product-auth-fixtures',
 use:{baseURL,headless:true,screenshot:'off',video:'off',trace:'off'},
 webServer:{command:'npm.cmd run dev -- --host 127.0.0.1 --port 52177 --strictPort',url:baseURL,reuseExistingServer:false,timeout:30_000},
});
