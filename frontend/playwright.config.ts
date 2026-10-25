import {defineConfig} from '@playwright/test';
export default defineConfig({testDir:'./tests',testMatch:'*.spec.ts',use:{viewport:{width:1366,height:768},headless:true},workers:1,webServer:{command:'node node_modules/vite/bin/vite.js --host 127.0.0.1',env:{VITE_P11_RESOURCES:'all'},url:'http://127.0.0.1:5174',reuseExistingServer:false}});
