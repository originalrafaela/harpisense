"""Opt-in administrative identity; never imported by the active bootstrap."""
from .service import AdminAuth, AuthError
from .api import install_admin_auth

__all__ = ['AdminAuth', 'AuthError', 'install_admin_auth']
