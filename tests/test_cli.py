"""CLI checks and isolated workflow tests; no AEDT installation is required."""
import contextlib
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from main import parse_args


class CliTests(unittest.TestCase):
    def test_desktop_and_section_options(self):
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder) / "test.aedt"
            sections = Path(folder) / "sections.txt"
            project.touch()
            sections.write_text("board = B Sphere_positions = 399 258")
            args = parse_args([str(project), "--desktop", "--sections", str(sections), "--extract-only", "--purge-history"])
            self.assertTrue(args.desktop and args.extract_only and args.purge_history)
            self.assertEqual(args.sections, sections)
            self.assertFalse(parse_args([str(project), "--extract"]).purge_history)

    def test_invalid_options_fail_before_loading_aedt(self):
        with tempfile.NamedTemporaryFile(suffix=".aedt") as project:
            for argv in ([project.name, "--extract-only"],
                         [project.name, "--purge-history"],
                         [project.name, "--extract", "--sections", "test.txt"],
                         [str(Path(project.name).with_suffix(".missing"))]):
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                    parse_args(argv)
                self.assertEqual(error.exception.code, 2)

    def test_extract_only_records_pins_without_duplicating_design_or_moving_originals(self):
        # Use a fresh interpreter so AEDT module substitutes cannot affect other tests.
        code = r'''
import importlib
from pathlib import Path
import sys
import types
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path('tests').resolve()))
from test_chips import chip_components
from Chips import ChipSection, CopyRecord, NumericalPositionFixed, TerminalPositionPair
from Chips.Generators import SectionCandidate
reader = types.ModuleType('AnsysSession.DesignReader')
reader.DesignReader = Mock()
sys.modules[reader.__name__] = reader
workflow = importlib.import_module('AnsysSession.Action.CopyandGenerate')
section = ChipSection(chip_components())
pair = TerminalPositionPair(NumericalPositionFixed.from_number(399, z=1.2),
                            NumericalPositionFixed.from_number(258, z=1.2))
candidate = SectionCandidate(section, pair)
session = Mock(design='D1')
record = CopyRecord('BOARD_1', 'D1', copies={f'source{i}': f'BOARD_1_obj{i}' for i in range(5)})
extraction = Mock(result=record)
extraction.act.return_value = 0
store = Mock(path=Path('copies.json'))
seen = []
with patch.object(workflow, 'ExtractCopy', return_value=extraction), \
     patch.object(workflow, 'switch_to_copy', side_effect=AssertionError('must not duplicate a design')), \
     patch.object(workflow, 'copy_chip', side_effect=AssertionError('must stay in the source design')), \
     patch.object(workflow, 'BzProcedure', side_effect=AssertionError('must not solve/export')), \
     patch.object(workflow, 'CheckValidity', side_effect=AssertionError('must not validate')), \
     patch.object(workflow, 'CopyStore', return_value=store), \
     patch.object(workflow, 'PurgeHistory') as purge, \
     patch('AnsysSession.Action.Action.ModelEditor') as editor:
    editor.return_value.set_pin_count.side_effect = AssertionError('must not change global pin variables')
    job = workflow.CopyandGenerate(session, candidate, extract_only=True)
    assert job.act() == 0, job.error
    editor.return_value.set_pin_count.assert_not_called()
    session.save.assert_called_once()
    saved = store.save.call_args.args[0]
    assert saved.pin_counts == {'VCC': 399, 'GND': 258}
    assert saved.analysis_design is None
    assert job.result['requested GND pin count'] == 258
    assert job.result['design'] == 'D1'
    assert 'copied in place' in job.result['placement']
    purge.assert_not_called()
    session.reset_mock()
    store.reset_mock()
    purge.return_value.act.return_value = 0
    purged = workflow.CopyandGenerate(session, candidate, extract_only=True, purge_history=True)
    assert purged.act() == 0, purged.error
    purge.assert_called_once_with(session.app, list(record.copies.values()))
    assert purged.result['history purged'] is True
    editor.return_value.set_pin_count.assert_not_called()
    session.save.assert_called_once()
    session.reset_mock()
    store.reset_mock()
    purge.return_value.act.return_value = 1
    purge.return_value.error = 'purge refused'
    purge.return_value.label = 'Purge_History'
    refused = workflow.CopyandGenerate(session, candidate, extract_only=True, purge_history=True)
    assert refused.act() == 1
    assert refused.failed.label == 'Purge_History'
    session.save.assert_not_called()
    store.save.assert_not_called()
    session.reset_mock()
    store.reset_mock()
    extraction.act.return_value = 1
    extraction.error = 'copy refused'
    failed = workflow.CopyandGenerate(session, candidate, extract_only=True)
    assert failed.act() == 1
    assert failed.failed is extraction
    session.save.assert_not_called()
    store.save.assert_not_called()
'''
        result = subprocess.run([sys.executable, "-B", "-c", code], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

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
from AnsysSession.Session import Session
desktop = sys.modules['ansys.aedt.core'].Desktop
session = Session('test.aedt', design='D1', non_graphical=False)
desktop.assert_called_once_with(non_graphical=False, new_desktop=True)
desktop.return_value.load_project.assert_called_once_with('test.aedt', design_name='D1')
session.release(close_desktop=False)
session.app.release_desktop.assert_called_once_with(close_projects=False, close_desktop=False)
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
