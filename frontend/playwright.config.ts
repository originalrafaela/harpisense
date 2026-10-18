import {defineConfig} from '@playwright/test';
export default defineConfig({testDir:'./tests',testMatch:'*.spec.ts',use:{viewport:{width:1366,height:768},headless:true},workers:1,webServer:{command:'npm.cmd run dev',url:'http://127.0.0.1:5173',reuseExistingServer:true}});
