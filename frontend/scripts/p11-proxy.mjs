// Local transport to an existing loopback API/tunnel. No API/business logic.
export function tunnelTarget(value = 'http://127.0.0.1:18000') {
  const url = new URL(value);
  if (url.protocol !== 'http:' || url.hostname !== '127.0.0.1' || url.username || url.password || url.pathname !== '/' || url.search || url.hash) {
    throw new Error('HARPI_API_TUNNEL_TARGET deve ser HTTP no loopback 127.0.0.1, sem caminho ou credenciais.');
  }
  return url.origin;
}

export function p11Transport(target) {
  const prefix = '/p11-api';
  const allowed = new Set(['health','asset','telemetry','network_event','window','detection','xai','evidence','incident','risk','decision','approval','execution','verification','bitnet'].map(kind=>`/api/v1/p11/${kind}`));
  allowed.add('/api/v1/security/settings/mode/default');allowed.add('/api/v1/security/audit');
  const guard = server => {server.middlewares.use((request, response, next) => {
    if (!request.url?.startsWith(prefix)) return next();
    const url = new URL(request.url, 'http://127.0.0.1');
    const path = url.pathname.slice(prefix.length);
    response.setHeader('Cache-Control', 'no-store');
    const origin = request.headers.origin;
    if (origin && origin !== `http://${request.headers.host}`) {
      response.writeHead(403, {'Content-Type': 'application/json'});
      return response.end('{"detail":"Origem não permitida no transporte local"}');
    }
    const authRoutes = new Map([['/api/v1/admin-auth/login','POST'],['/api/v1/admin-auth/session','GET'],['/api/v1/admin-auth/logout','POST'],['/api/v1/admin-auth/password','PUT'],['/api/v1/admin-auth/username','PUT']]);
    const auth = authRoutes.get(path) === request.method;
    // The browser transport has no technical Basic or service-ingestion path.
    if (request.headers.authorization && !/^Bearer [A-Za-z0-9_-]{43}$/.test(request.headers.authorization)) {
      response.writeHead(401, {'Content-Type':'application/json','WWW-Authenticate':'Bearer'});
      return response.end('{"error":{"code":"AUTH_REQUIRED"}}');
    }
    const read=request.method==='GET'&&(allowed.has(path)||/^\/api\/v1\/p11\/explain\/[A-Za-z0-9_.:@-]{1,128}$/.test(path)||/^\/api\/v1\/p11\/bitnet\/[A-Za-z0-9_.:@-]{1,128}\/history$/.test(path));
    const write=(request.method==='PUT'&&path==='/api/v1/security/settings/mode/default')||(request.method==='POST'&&path==='/api/v1/security/emergency-stop');
    if (!read&&!write&&!auth) {
      response.writeHead(request.method !== 'GET' ? 405 : 404, {'Content-Type': 'application/json'});
      return response.end('{"detail":"Recurso não integrado neste transporte restrito"}');
    }
    // Only pagination fields documented by P11; reject arbitrary URL parameters.
    if (((write||auth)&&url.search)||[...url.searchParams.keys()].some(key => !['limit', 'offset'].includes(key))) {
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
          // Session is explicit Bearer in memory; never create browser cookies.
          delete response.headers['set-cookie'];
        });
        proxy.on('proxyReq', request => {request.removeHeader('cookie')});
        proxy.on('error', (_error, _request, response) => {
          if (!response.headersSent && typeof response.writeHead === 'function') {
            response.writeHead(503, {'Content-Type':'application/json','Cache-Control':'no-store'});
            response.end('{"error":{"code":"TRANSPORT_UNAVAILABLE"}}');
          }
        });
      },
    }},
  };
}
