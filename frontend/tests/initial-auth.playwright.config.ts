import {defineConfig} from '@playwright/test';
export default defineConfig({testDir:'.',testMatch:'initial-auth-ui.spec.ts',workers:1,
 use:{baseURL:'http://127.0.0.1:5190',headless:true,screenshot:'off',trace:'off',video:'off'},
 webServer:process.env.HARPI_TEST_EXTERNAL_SERVER?undefined:{cwd:process.cwd(),command:'node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5190',url:'http://127.0.0.1:5190',reuseExistingServer:false},
});
