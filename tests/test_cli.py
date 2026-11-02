"""Settings checks and isolated workflow tests; no AEDT installation is required."""
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest

import configs
from main import bz_options, check_settings


def settings(**changes):
    """configs.py's settings with ``changes`` applied, without touching the module."""
    values = {name: getattr(configs, name) for name in dir(configs) if name.isupper()}
    return types.SimpleNamespace(**{**values, **changes})


class CliTests(unittest.TestCase):
    def test_valid_settings_pass(self):
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder) / "test.aedt"
            sections = Path(folder) / "sections.txt"
            project.touch()
            sections.write_text("board = B Sphere_positions = 399 258")
            check_settings(settings(DEFAULT_INPUT_PATH=str(project), RUN_MODE="sections", SECTIONS_FILE=str(sections),
                                    SHOW_DESKTOP=True))
            check_settings(settings(DEFAULT_INPUT_PATH=str(project), RUN_MODE="analyse"))

    def test_invalid_settings_fail_before_loading_aedt(self):
        with tempfile.NamedTemporaryFile(suffix=".aedt") as project:
            for changes in (dict(RUN_MODE="sections", SECTIONS_FILE="test.txt"),
                            dict(RUN_MODE="copy"),
                            dict(DEFAULT_INPUT_PATH=str(Path(project.name).with_suffix(".missing"))),
                            dict(DEFAULT_INPUT_PATH="")):
                with self.subTest(**changes), self.assertRaises(ValueError):
                    check_settings(settings(**{"DEFAULT_INPUT_PATH": project.name, **changes}))

    def test_bz_options_come_from_the_settings(self):
        options = bz_options(settings(CORES=8, SOLVE=False, DEFAULT_SETUP="Setup2"))
        self.assertEqual((options["cores"], options["solve"], options["setup"]), (8, False, "Setup2"))
        self.assertEqual(options["step"], configs.DEFAULT_GRID_STEP)

    def test_session_forwards_gui_and_keep_open_options(self):
        code = r'''
import sys
import types
from unittest.mock import Mock
for name, member in [('ansys.aedt.core', 'Desktop'),
                     ('AnsysSession.DesignReader', 'DesignReader'),
                     ('AnsysSession.Report', 'ProjectReport')]:
    module = types.ModuleType(name)
    setattr(module, member, Mock())
    sys.modules[name] = module
desktop_module = types.ModuleType('ansys.aedt.core.desktop')
desktop_module.is_grpc_session_active = Mock(return_value=True)
sys.modules[desktop_module.__name__] = desktop_module
from AnsysSession.Session import Session
desktop = sys.modules['ansys.aedt.core'].Desktop
session = Session('test.aedt', design='D1', non_graphical=False)
desktop.assert_called_once_with(non_graphical=False, new_desktop=True)
desktop.return_value.load_project.assert_called_once_with('test.aedt', design_name='D1')
session.release(close_desktop=False)
desktop.return_value.load_project.return_value.release_desktop.assert_called_once_with(close_projects=False, close_desktop=False)
'''
        result = subprocess.run([sys.executable, "-B", "-c", code], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_snapshot_uses_live_boundary_assignments_without_project_parse(self):
        code = r'''
import sys
import types
from unittest.mock import Mock
material_module = types.ModuleType('ansys.aedt.core.modules.material')
material_module.MatProperties = Mock()
sys.modules[material_module.__name__] = material_module
from AnsysSession.DesignReader import DesignReader
class LiveBoundary:
    type = 'Current'
    def __init__(self, name):
        self.name = name
        self.properties = {'Name': name, 'Current': '1A'}
    @property
    def props(self):
        raise AssertionError('full-project boundary parser accessed')
class LiveApp:
    design_name = 'D1'
    boundaries = [LiveBoundary('Current1'), LiveBoundary('Current2')]
    @property
    def materials(self):
        raise AssertionError('material registry accessed')
    @property
    def project_properties(self):
        raise AssertionError('saved project parser accessed')
app = LiveApp()
app.modeler = Mock(object_names=['VCC', 'GND'], model_units='mm')
editor = app.modeler.oeditor
editor.GetObjectsInGroup.side_effect = lambda group: ['VCC', 'GND'] if group == 'Solids' else []
editor.GetFaceIDs.side_effect = lambda name: [11] if name == 'VCC' else [21]
editor.GetObjectBoundingBox.return_value = [0,0,0,1,1,1]
editor.GetFaceCenter.return_value = [0.5,0.5,1]
editor.GetChildNames.return_value = []
editor.GetObjectsByMaterial.return_value = ['VCC','GND']
editor.GetObjectNameByID.return_value = 'GND'
app.odefinition_manager = Mock()
app.odefinition_manager.GetProjectMaterialNames.return_value = ['copper']
app.oboundary = Mock()
app.oboundary.GetAssignment.side_effect = lambda name: ['11'] if name == 'Current1' else ['100']
snapshot = DesignReader(app).snapshot()
vcc = snapshot.get_component('VCC')
gnd = snapshot.get_component('GND')
assert vcc.material_name == 'copper'
assert vcc.boundaries[0].faces == (11,)
assert vcc.boundaries[0].center == (0.5,0.5,1.0)
assert gnd.boundaries[0].objects == ('GND',)
assert gnd.boundaries[0].center is None
editor.GetFaceIDs.assert_any_call('VCC')
assert editor.GetFaceIDs.call_count == 2
'''
        result = subprocess.run([sys.executable, "-B", "-c", code], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
