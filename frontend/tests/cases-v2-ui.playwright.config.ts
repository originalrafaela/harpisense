import {defineConfig} from '@playwright/test';
export default defineConfig({testDir:'.',testMatch:'tests/cases-v2-ui.spec.ts',workers:1,use:{viewport:{width:1280,height:800},headless:true,screenshot:'off',video:'off',trace:'off'}});
