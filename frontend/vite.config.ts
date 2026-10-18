import {defineConfig, loadEnv} from 'vite';
// @ts-ignore Plain Node module, also exercised by the transport tests.
import {p11Transport} from './scripts/p11-proxy.mjs';

export default defineConfig(({mode}) => {
  const env = loadEnv(mode, process.cwd(), 'HARPI_');
  const transport = p11Transport(env.HARPI_API_TUNNEL_TARGET);
  return {
    plugins: [transport.plugin],
    server: {host: '127.0.0.1', port: 5174, strictPort: true, cors: false, proxy: transport.proxy},
    preview: {host: '127.0.0.1', port: 4174, strictPort: true, cors: false, proxy: transport.proxy},
  };
});
