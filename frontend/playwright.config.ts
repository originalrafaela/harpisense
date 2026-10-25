import {defineConfig} from '@playwright/test';
export default defineConfig({
  testDir:'./tests', testMatch:'*.spec.ts', workers:1,
  use:{viewport:{width:1366,height:768},headless:true},
  globalSetup:'./tests/global-setup.mjs',
});
