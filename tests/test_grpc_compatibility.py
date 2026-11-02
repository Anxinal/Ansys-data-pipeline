"""Connection metadata stays local; actual remote property writes stay intact."""
from contextlib import contextmanager
import sys
import types
import unittest
from unittest.mock import patch

from AnsysSession.GrpcCompatibility import local_grpc_metadata, local_grpc_port_detection


class GrpcCompatibilityTests(unittest.TestCase):
    def test_new_desktop_can_detect_its_dynamically_assigned_port(self):
        from unittest.mock import Mock, MagicMock
        module = types.ModuleType('ansys.aedt.core.desktop')
        original = Mock(return_value=False)
        module.is_grpc_session_active = original
        with patch.dict(sys.modules,{module.__name__:module}), \
             patch('AnsysSession.GrpcCompatibility.socket.create_connection',return_value=MagicMock()):
            with local_grpc_port_detection():
                self.assertTrue(module.is_grpc_session_active(55900,'127.0.0.1'))
                self.assertFalse(module.is_grpc_session_active(0))
            self.assertIs(module.is_grpc_session_active,original)

    def test_port_fallback_is_limited_to_selected_local_port_and_restored(self):
        from unittest.mock import Mock, MagicMock
        module = types.ModuleType('ansys.aedt.core.desktop')
        original = Mock(return_value=False)
        module.is_grpc_session_active = original
        with patch.dict(sys.modules, {module.__name__:module}), \
             patch('AnsysSession.GrpcCompatibility.socket.create_connection',return_value=MagicMock()) as connect:
            with self.assertRaisesRegex(RuntimeError,'done'):
                with local_grpc_port_detection(64286):
                    self.assertTrue(module.is_grpc_session_active(64286,'127.0.0.1'))
                    self.assertFalse(module.is_grpc_session_active(50000))
                    self.assertFalse(module.is_grpc_session_active(64286,'remote-server'))
                    connect.assert_called_once_with(('127.0.0.1',64286),timeout=1)
                    raise RuntimeError('done')
            self.assertIs(module.is_grpc_session_active,original)

    def test_unreachable_selected_port_is_not_reported_as_active(self):
        from unittest.mock import Mock
        module = types.ModuleType('ansys.aedt.core.desktop')
        module.is_grpc_session_active = Mock(return_value=False)
        with patch.dict(sys.modules,{module.__name__:module}), \
             patch('AnsysSession.GrpcCompatibility.socket.create_connection',side_effect=OSError('refused')):
            with local_grpc_port_detection(64286):
                self.assertFalse(module.is_grpc_session_active(64286))

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
