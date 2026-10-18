// Local read-only transport to an existing SSH tunnel. No API/business logic.
export function tunnelTarget(value = 'http://127.0.0.1:18000') {
  const url = new URL(value);
  if (url.protocol !== 'http:' || url.hostname !== '127.0.0.1' || url.username || url.password || url.pathname !== '/' || url.search || url.hash) {
    throw new Error('HARPI_API_TUNNEL_TARGET deve ser HTTP no loopback 127.0.0.1, sem caminho ou credenciais.');
  }
  return url.origin;
}

export function p11Transport(target) {
  const prefix = '/p11-api';
  const allowed = new Set(['/api/v1/p11/health', '/api/v1/p11/telemetry']);
  const guard = server => {server.middlewares.use((request, response, next) => {
    if (!request.url?.startsWith(prefix)) return next();
    const url = new URL(request.url, 'http://127.0.0.1');
    const path = url.pathname.slice(prefix.length);
    const origin = request.headers.origin;
    if (origin && origin !== `http://${request.headers.host}`) {
      response.writeHead(403, {'Content-Type': 'application/json'});
      return response.end('{"detail":"Origem não permitida no transporte local"}');
    }
    if (request.method !== 'GET' || !allowed.has(path)) {
      response.writeHead(request.method !== 'GET' ? 405 : 404, {'Content-Type': 'application/json'});
      return response.end('{"detail":"Recurso não integrado neste transporte de leitura"}');
    }
    // Only pagination fields documented by P11; reject arbitrary URL parameters.
    if ([...url.searchParams.keys()].some(key => !['limit', 'offset'].includes(key))) {
      response.writeHead(400, {'Content-Type': 'application/json'});
      return response.end('{"detail":"Parâmetro não permitido"}');
    }
    next();
  });};
  return {
    plugin: {name: 'harpisense-local-read-transport', configureServer: guard, configurePreviewServer: guard},
    proxy: {[prefix]: {
      target: tunnelTarget(target), changeOrigin: false, followRedirects: false,
      timeout: 10000, proxyTimeout: 9000, rewrite: path => path.slice(prefix.length),
      configure(proxy) {
        proxy.on('proxyRes', response => {
          response.headers['cache-control'] = 'no-store';
          // Explicit frontend Basic auth; do not let the transport create browser cookies.
          delete response.headers['set-cookie'];
        });
      },
    }},
  };
}
