"""Driver fixture: window closure is normal; a live driver's real failure propagates.

This validates launcher control flow only, not Chromium, cookies or UI integration.
"""
from types import ModuleType, SimpleNamespace
import sys
import unittest
from unittest.mock import patch

from backend.local_activation.ipc import launch_first_use


class DriverError(Exception):
    pass


class BrowserLifecycleTests(unittest.TestCase):
    def launch(self, *, close_during_navigation=False, close_during_wait=False, failure=False):
        state = dict(closed=False, cleanup=False)
        context = SimpleNamespace(pages=[], add_cookies=lambda cookies: None)

        def goto(url):
            if close_during_navigation:
                context.pages.clear()
                state['closed'] = True
                raise DriverError('TargetClosedError fixture')

        def wait(timeout):
            if close_during_wait:
                context.pages.clear()
                raise DriverError('TargetClosedError fixture')
            if failure:
                raise DriverError('live driver failure fixture')

        page = SimpleNamespace(goto=goto, wait_for_timeout=wait)
        context.new_page = lambda: page
        context.pages = [page]

        def close():
            state['cleanup'] = True
            state['closed'] = True

        browser = SimpleNamespace(is_connected=lambda: not state['closed'], close=close,
                                  new_context=lambda: context)
        manager = SimpleNamespace(chromium=SimpleNamespace(launch=lambda **kwargs: browser))

        class Scope:
            def __enter__(self):
                return manager

            def __exit__(self, *args):
                return False

        module = ModuleType('playwright.sync_api')
        module.sync_playwright = Scope
        module.Error = DriverError
        with patch.dict(sys.modules, {'playwright': ModuleType('playwright'),
                                      'playwright.sync_api': module}):
            launch_first_use(dict(origin='http://127.0.0.1:18080', cookie_name='hs_initial_access',
                cookie_value='fixture', cookie_path='/p11-api/api/v1/', expires_at=2000000000),
                chromium_executable='fixture-browser')
        return state

    def test_close_while_loading_is_normal_completion(self):
        self.assertTrue(self.launch(close_during_navigation=True)['closed'])

    def test_close_last_page_is_normal_and_releases_browser(self):
        self.assertTrue(self.launch(close_during_wait=True)['cleanup'])

    def test_live_driver_failure_is_not_silenced(self):
        with self.assertRaisesRegex(DriverError, 'live driver failure'):
            self.launch(failure=True)
