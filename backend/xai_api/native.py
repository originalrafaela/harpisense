"""Single native-runtime hook, with no migrations, model loading or side effects."""
from delivery.postgres_store import PostgresStore
from .api import install_xai_api


def install_on_native(app, state):
    """Call after /p11-api is mounted in native_server.runtime.build_native_app."""
    api = next(route.app for route in app.routes if getattr(route,'path',None)=='/p11-api')
    if getattr(api.state,'xai_reader',None):
        return api.state.xai_reader
    return install_xai_api(api,PostgresStore(state['dsn']),installation_id=state['installation_id'],
                           asset_identifier_column='device_id')
