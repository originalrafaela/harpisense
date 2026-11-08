import {defineConfig} from '@playwright/test';

process.env.HARPISENSE_TEST_URL='http://127.0.0.1:5176';

export default defineConfig({
  testDir:'.',
  testMatch:['tests/recovery-welcome.spec.ts','tests/operational-review.spec.ts','tests/config-manager.spec.ts','tests/installation-entry.spec.ts'],
  workers:1,
  use:{viewport:{width:1280,height:800},headless:true,screenshot:'off',video:'off',trace:'off'},
});
