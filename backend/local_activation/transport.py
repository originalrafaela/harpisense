"""Request attestation produced only by a dedicated native ASGI listener.

Wrap the app ONLY on the strict loopback listener. Never mount this wrapper behind
a network proxy. The network-facing app must keep the unattested scope. Even on
this listener the separate IPC-issued cookie is required on every initial action.
"""
import ipaddress


class NativeTransport:
    def __init__(self, host='127.0.0.1', port=18080):
        if host not in ('127.0.0.1', '::1'):
            raise ValueError('LOOPBACK_LISTENER_REQUIRED')
        self.address = (host, port)
        self._seal = object()

    def authorized(self, request):
        return request.scope.get('harpisense.native_transport') is self._seal

    def wrap(self, app):
        seal, address = self._seal, self.address

        async def native_app(scope, receive, send):
            scope = dict(scope)
            scope.pop('harpisense.native_transport', None)
            if scope['type'] in ('http', 'websocket'):
                client = scope.get('client')
                server = scope.get('server')
                headers = [(k.lower(), v) for k, v in scope.get('headers', [])]
                # Refuse proxy protocols/headers; Uvicorn proxy_headers MUST be disabled.
                forwarded = any(k in (b'forwarded', b'x-forwarded-for', b'x-forwarded-host',
                                      b'x-forwarded-proto') for k, _ in headers)
                try:
                    local = bool(client) and ipaddress.ip_address(client[0]).is_loopback
                except ValueError:
                    local = False
                if forwarded or not local or tuple(server or ()) != address:
                    if scope['type'] == 'websocket':
                        await send({'type': 'websocket.close', 'code': 1008})
                    else:
                        await send({'type': 'http.response.start', 'status': 403,
                                    'headers': [(b'cache-control', b'no-store')]})
                        await send({'type': 'http.response.body', 'body': b''})
                    return
                scope['harpisense.native_transport'] = seal
            await app(scope, receive, send)
        return native_app
