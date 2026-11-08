"""Installed-machine primitives; wire protocol is owned by activation contract."""
from .protection import ProtectionError, SystemdCredential, WindowsDPAPI

__all__ = ['InstallationIdentity', 'load_totp_key', 'provision_totp_key',
           'ProtectionError', 'SystemdCredential', 'WindowsDPAPI']


def __getattr__(name):
    # IPC/launcher lifecycle needs only the standard library. Defer crypto loading
    # until a consumer actually requests identity operations; no plaintext fallback.
    if name in ('InstallationIdentity', 'load_totp_key', 'provision_totp_key'):
        from . import identity
        return getattr(identity, name)
    raise AttributeError(name)
