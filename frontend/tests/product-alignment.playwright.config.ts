import {defineConfig} from '@playwright/test';
export default defineConfig({testDir:'.',testMatch:'tests/product-alignment.spec.ts',workers:1,use:{viewport:{width:1366,height:768},headless:true,screenshot:'off',video:'off',trace:'off'}});
