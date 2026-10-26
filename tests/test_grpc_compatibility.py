"""Connection metadata stays local; actual remote property writes stay intact."""
from contextlib import contextmanager
import sys
import types
import unittest
from unittest.mock import patch

from AnsysSession.GrpcCompatibility import local_grpc_metadata


class GrpcCompatibilityTests(unittest.TestCase):
    def test_scoped_metadata_and_property_delegation(self):
        writes = []

        class Proxy:
            def __setattr__(self, name, value):
                writes.append((name, value))
                if name == "AedtAPI":
                    raise AssertionError("remote GetPropNames path")
                object.__setattr__(self, name, value)

        module = types.ModuleType('ansys.aedt.core.internal.grpc_plugin_dll_class')
        module.AedtPropServer = Proxy
        original = Proxy.__setattr__
        proxy = Proxy()
        with patch.dict(sys.modules, {module.__name__: module}), \
             patch('AnsysSession.GrpcCompatibility.version', return_value='1.0.1'):
            with self.assertRaisesRegex(RuntimeError, 'test failure'):
                with local_grpc_metadata():
                    proxy.AedtAPI = 'connection'
                    proxy.Material = 'copper'
                    outer = Proxy.__setattr__
                    with local_grpc_metadata():
                        proxy.AedtAPI = 'nested connection'
                    self.assertIs(Proxy.__setattr__, outer)
                    raise RuntimeError('test failure')
            self.assertIs(Proxy.__setattr__, original)
        self.assertEqual(writes, [('Material', 'copper')])
        self.assertEqual(proxy.AedtAPI, 'nested connection')
        self.assertEqual(proxy.Material, 'copper')

    def test_other_versions_do_not_install_guard(self):
        with patch('AnsysSession.GrpcCompatibility.version', return_value='1.0.2'):
            with local_grpc_metadata():
                self.assertFalse('ansys.aedt.core.internal.grpc_plugin_dll_class' in sys.modules)


if __name__ == '__main__':
    unittest.main()
