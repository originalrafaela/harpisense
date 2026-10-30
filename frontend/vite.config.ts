import {defineConfig, loadEnv} from 'vite';
// @ts-ignore Plain Node module, also exercised by the transport tests.
import {p11Transport} from './scripts/p11-proxy.mjs';

export default defineConfig(({mode}) => {
  const env = loadEnv(mode, process.cwd(), 'HARPI_');
  const transport = p11Transport(env.HARPI_API_TUNNEL_TARGET);
  const headers = {'Referrer-Policy':'no-referrer','X-Content-Type-Options':'nosniff',
    'Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self' https: ws://127.0.0.1:5174; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"};
  return {
    plugins: [transport.plugin],
    server: {host: '127.0.0.1', port: 5174, strictPort: true, cors: false, headers, proxy: transport.proxy},
    preview: {host: '127.0.0.1', port: 4174, strictPort: true, cors: false, headers, proxy: transport.proxy},
  };
});
