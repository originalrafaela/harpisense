import {defineConfig} from '@playwright/test';
export default defineConfig({
 testDir:'.',testMatch:'installation-entry.browser.ts',workers:1,
 use:{baseURL:'http://127.0.0.1:5186',headless:true},
 globalSetup:'./installation-global-setup.mjs',
});
