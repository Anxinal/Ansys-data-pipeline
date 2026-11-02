"""The action base class, and Session as the only way into AEDT, on fake AEDT apps; no AEDT needed."""
from pathlib import Path
import re
import subprocess
import sys
import unittest


STUBS = r'''
import sys
import types
from unittest.mock import Mock
material = types.ModuleType('ansys.aedt.core.modules.material')
material.MatProperties = Mock()
sys.modules[material.__name__] = material
'''

# A real Session, DesignReader and ModelEditor on a fake app whose model flags and history behave like AEDT's.
FAKE_SESSION = STUBS + r'''
core = types.ModuleType('ansys.aedt.core')
core.Desktop = Mock()
core.settings = types.SimpleNamespace(release_on_exception=True)
sys.modules[core.__name__] = core
desktop_module = types.ModuleType('ansys.aedt.core.desktop')
desktop_module.is_grpc_session_active = Mock(return_value=True)
sys.modules[desktop_module.__name__] = desktop_module
from AnsysSession.Session import Session

session = Session('test.aedt')
app = core.Desktop.return_value.load_project.return_value
app.design_name = 'D1'
native = app.modeler.oeditor
groups = {'Solids': ['A', 'B', 'Region'], 'Sheets': ['C'], 'Lines': [], 'Non Model': ['C']}
native.GetObjectsInGroup.side_effect = lambda group: list(groups[group])
native.GetObjectsByMaterial.side_effect = lambda material: ['Region'] if material == 'vacuum' else []

def change_flags(arguments):
    tab = arguments[1]
    if tab[0] == 'NAME:Geometry3DAttributeTab':
        names, model = tab[1][1:], tab[2][1][2]
        groups['Non Model'] = sorted((set(groups['Non Model']) - set(names)) | (set() if model else set(names)))

native.ChangeProperty.side_effect = change_flags
native.GetObjectBoundingBox.return_value = [0, 0, 0, 1, 1, 1]
'''


# A step for IsolatedProcedure that records what is active, on the fake session above.
ISOLATION = r'''
import json, tempfile
from pathlib import Path
from AnsysSession.Action.Action import AnsysAction
from AnsysSession.Action.SelectAndAnalyseWorkflow.IsolatedProcedure import IsolatedProcedure
from AnsysSession.Action.SelectAndAnalyseWorkflow.SelectForAnalysis import BoardSelect
from Chips.Components import Component

app.odesign.GetVariableValue.side_effect = lambda name: '7'
state_file = Path(tempfile.mkdtemp()) / 'state.json'
active = []

class Step(AnsysAction):
    def __init__(self, session, label, fails=False):
        super().__init__(session, label)
        self.fails = fails
    def act(self):
        names, modeled = session.model_objects()
        active.append(sorted(modeled))
        if self.fails:
            raise KeyError('solve failed')
        return self.SUCCESS
'''


# A source design with two boards, for RootAnalysis on the fake session above.
ROOT_ANALYSIS = r'''
import json, tempfile
from pathlib import Path
from AnsysSession.Action.Action import ActionFailed
from AnsysSession.Action.SelectAndAnalyseWorkflow.RootAnalysis import RootAnalysis

folder = Path(tempfile.mkdtemp())
run_dir, sections = folder / 'run', folder / 'sections.txt'
settings = types.SimpleNamespace(SECTIONS_FILE=sections, DEFAULT_GND='GND', DEFAULT_VCC='VCC',
                                 DEFAULT_SPEHRE=['Sphere_GND', 'Sphere_VCC'])
options = dict(setup='Setup1', output_dir='unused', scan_height=0.06, step=0.5, cores=None, solve=True)
groups['Solids'] = ['BoardA', 'BoardB', 'VCC', 'GND', 'Sphere_GND', 'Sphere_VCC', 'Region', 'Other']
values = {'PinCount': '7', 'PinCountGND': '8'}
app.odesign.GetVariableValue.side_effect = lambda name: values[name]
def set_variable(arguments):
    name, _, expression = arguments[1][2][1]
    values[name[len('NAME:'):]] = expression
app.odesign.ChangeProperty.side_effect = set_variable
app.working_directory = str(folder)
app.setup_names = ['Setup1']
app.analyze_setup.return_value = True
app.project_name, app.modeler.model_units = 'P', 'mm'
app.existing_analysis_sweeps = ['Setup1 : LastAdaptive']
app.variable_manager.independent_design_variables = {}
def write_grid(path, *arguments):
    with open(path, 'w') as stream:
        stream.write('0 0 1 0.001\n1 0 1 0.002\n0 1 1 0.003\n1 1 1 0.004\n' * 5)
app.ofieldsreporter.ExportOnGrid.side_effect = write_grid
seen, verdicts = [], [1] * 10
def validate(log_file):
    seen.append((list(groups['Non Model']), dict(values)))
    return verdicts.pop(0)
app.validate_simple.side_effect = validate
selected, select = [], session.select_for_analysis
session.select_for_analysis = lambda name: (selected.append(name), select(name))[1]
'''


class ActionTests(unittest.TestCase):
    def run_isolated(self, code):
        result = subprocess.run([sys.executable, '-B', '-c', STUBS + code], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_run_returns_the_result_or_raises_naming_the_failed_step(self):
        self.run_isolated(r'''
from AnsysSession.Action.Action import ActionFailed, AnsysAction, AnsysProcedure

class Step(AnsysAction):
    def __init__(self, label, ok=True):
        super().__init__(Mock(), label)
        self.ok = ok
    def act(self):
        if not self.ok:
            self.error = 'refused'
            return self.FAILURE
        self.result = self.label
        return self.SUCCESS

assert Step('one').run() == 'one'
try:
    Step('lonely', ok=False).run()
    raise AssertionError('no ActionFailed')
except ActionFailed as e:
    assert str(e) == 'lonely failed: refused', e
procedure = AnsysProcedure([Step('first'), Step('second', ok=False), Step('third')], Mock(), 'proc')
try:
    procedure.run()
    raise AssertionError('no ActionFailed')
except ActionFailed as e:
    assert str(e) == 'second failed: refused', e
assert procedure.failed.label == 'second'
''')

    def test_generate_snapshot_returns_the_cropped_board_image(self):
        self.run_isolated(r'''
import tempfile
import numpy as np
from PIL import Image
import AnsysSession.DesignReader as design_reader
from AnsysSession.Action.GenerateSnapshot import GenerateSnapshot

class Editor:
    def __init__(self, draw):
        self.draw = draw
    def ShowWindow(self):
        pass
    def FitAll(self):
        pass
    def ExportModelImageToFile(self, full_name, width, height, arguments):
        options = dict(zip(arguments[1::2], arguments[2::2]))
        assert options['Orientation:='] == 'bottom' and options['Selections:='] == 'Board', options
        assert options['FieldPlotSelections:='] == 'none', options
        if self.draw:  # gradient background with a 75 x 40 board at (30, 20)
            pixels = np.linspace(200, 255, 120)[:, None, None] * np.ones((1, 160, 3))
            pixels[20:60, 30:105] = [40, 120, 40]
            Image.fromarray(pixels.astype(np.uint8)).save(full_name, quality=90)
        return str(full_name)

class App:
    @property
    def post(self):
        raise AssertionError('Snapshot must not initialize postprocessing or parse the project')

folder = tempfile.mkdtemp()
app = App()
app.working_directory = folder
app.design_name = 'Maxwell 3D: copy'
app.desktop_class = types.SimpleNamespace(non_graphical=False)
app.modeler = types.SimpleNamespace(oeditor=Editor(True))
session = Mock()
session.obtain_image_snapshot = design_reader.DesignReader(app).obtain_image_snapshot
board = Mock()
board.name = 'Board'
design_reader.GRID_SIZE = [10, 10]
image = GenerateSnapshot(session, board).run()
assert image.image.size == (75, 40), image.image.size
assert (image.name, len(image.split_all())) == ('Board', 7 * 4)

app.modeler.oeditor = Editor(False)
action = GenerateSnapshot(session, board)
assert action.act() == action.FAILURE and 'graphical mode' in action.error, action.error
app.desktop_class.non_graphical = True
action = GenerateSnapshot(session, board)
assert action.act() == action.FAILURE and 'graphical mode' in action.error, action.error
design_reader.GRID_SIZE = []
action = GenerateSnapshot(session, board)
assert action.act() == action.FAILURE and 'GRID_SIZE' in action.error, action.error
''')


class SessionTests(unittest.TestCase):
    def run_isolated(self, code):
        result = subprocess.run([sys.executable, '-B', '-c', FAKE_SESSION + code], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_session_hides_the_app_reader_and_editor(self):
        self.run_isolated(r'''
for name in ('app', 'reader', 'editor'):
    assert not hasattr(session, name), name
session.save()
app.save_project.assert_called_once()
''')

    def test_only_session_and_its_collaborators_touch_aedt(self):
        root = Path(__file__).resolve().parent.parent
        allowed = {"Session.py", "DesignReader.py", "ModelEditor.py", "Report.py"}
        sources = [root / "main.py", *(root / "AnsysSession").rglob("*.py")]
        for path in (p for p in sources if p.name not in allowed):
            self.assertIsNone(re.search(r"\.(app|_app|reader|_reader|editor|_editor)\b", path.read_text()), path)

    def test_deselect_all_for_analysis_makes_every_object_inactive(self):
        self.run_isolated(r'''
import json, tempfile
from pathlib import Path
from AnsysSession.ModelEditor import AedtError
from AnsysSession.Action.SelectAndAnalyseWorkflow.RestoreState import RestoreState
app.odesign.GetVariableValue.side_effect = lambda name: '7'
state_file = Path(tempfile.mkdtemp()) / 'state.json'
session._snapshot = 'stale'
state = session.deselect_all_for_analysis(['A'], state_file)
assert groups['Non Model'] == ['A', 'B', 'C', 'Region'], groups
assert session._snapshot is None
saved = json.loads(state_file.read_text())
assert saved['model_objects'] == ['A', 'B', 'Region'] and saved['selected'] == ['A'], saved
assert RestoreState(session, state_file).run()['restored']
assert groups['Non Model'] == ['C'], groups
native.ChangeProperty.side_effect = None  # AEDT ignores the change
try:
    session.deselect_all_for_analysis(['A'], state_file)
    raise AssertionError('no AedtError')
except AedtError as e:
    assert 'did not apply' in str(e), e
''')

    def test_select_for_analysis_makes_one_object_active(self):
        self.run_isolated(r'''
groups['Non Model'] = ['A', 'B', 'C', 'Region']
session._snapshot = 'stale'
session.select_for_analysis('B')
assert groups['Non Model'] == ['A', 'C', 'Region'], groups
assert session._snapshot is None
session.select_for_analysis('B')  # already active: nothing changes
assert groups['Non Model'] == ['A', 'C', 'Region'], groups
try:
    session.select_for_analysis('Missing')
    raise AssertionError('no LookupError')
except LookupError as e:
    assert 'Missing' in str(e), e
assert groups['Non Model'] == ['A', 'C', 'Region'], groups
''')

    def test_board_update_swaps_one_board_for_another(self):
        self.run_isolated(r'''
from AnsysSession.Action.SelectAndAnalyseWorkflow.SelectForAnalysis import BoardUpdate
from Chips.Components import Component
groups['Non Model'] = ['B', 'C']
BoardUpdate(session, Component('A'), Component('B')).run()
assert groups['Non Model'] == ['A', 'C'], groups
''')

    def test_select_necessary_components_selects_the_terminals_and_spheres(self):
        self.run_isolated(r'''
from AnsysSession.Action.SelectAndAnalyseWorkflow.SelectForAnalysis import SelectNecessaryComponents
parts = ['GND', 'VCC', 'Sphere_GND', 'Sphere_VCC']
groups.update({'Solids': [*parts, 'Board'], 'Non Model': [*parts, 'Board']})
SelectNecessaryComponents(session).run()
assert groups['Non Model'] == ['Board'], groups
''')

    def test_actions_load_without_pyaedt(self):
        code = "import sys; import AnsysSession.Action.SelectAndAnalyseWorkflow.SelectForAnalysis; assert 'ansys.aedt.core' not in sys.modules"
        result = subprocess.run([sys.executable, '-B', '-c', code], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_board_select_takes_components_only(self):
        self.run_isolated(r'''
from AnsysSession.Action.SelectAndAnalyseWorkflow.SelectForAnalysis import BoardSelect
from Chips.Components import Component
groups['Non Model'] = ['A', 'B', 'C', 'Region']
action = BoardSelect(session, [Component('A'), Component('B')])
assert action.names == ['A', 'B'], action.names
assert action.act() == action.SUCCESS and groups['Non Model'] == ['C', 'Region'], groups
for wrong in (['A'], [Component('A'), 'B']):
    try:
        BoardSelect(session, wrong)
        raise AssertionError('no TypeError')
    except TypeError as e:
        assert 'needs Components' in str(e), e
''')

    def test_isolated_procedure_restores_after_a_failure(self):
        self.run_isolated(ISOLATION + r'''
steps = [BoardSelect(session, [Component('A')]), Step(session, 'solve', fails=True)]
job = IsolatedProcedure(['A'], state_file, steps, session)
assert job.act() == job.FAILURE and job.failed.label == 'solve', job.failed
assert job.error == "KeyError: 'solve failed'", job.error
assert active == [['A', 'Region']], active
assert groups['Non Model'] == ['C'], groups
state = json.loads(state_file.read_text())
assert state['restored'] and state['background'] == ['Region'], state
assert state['pin_expressions'] == {'PinCount': '7', 'PinCountGND': '7'}, state
''')

    def test_isolated_procedure_changes_nothing_for_an_unknown_object(self):
        self.run_isolated(ISOLATION + r'''
state_file.write_text('{"stale": true}')
job = IsolatedProcedure(['Missing'], state_file, [Step(session, 'solve')], session)
assert job.act() == job.FAILURE and job.failed.label == 'Deselect_All', job.failed
assert 'Missing' in job.error and job.restore.result is None and active == [], job.error
assert groups['Non Model'] == ['C'] and not state_file.exists(), groups
''')

    def test_isolated_procedure_reports_a_failed_restoration(self):
        self.run_isolated(ISOLATION + r'''
def refuse_pins(arguments):
    raise RuntimeError('pins refused')
app.odesign.ChangeProperty.side_effect = refuse_pins
for fails, label in ((False, 'Restore_State'), (True, 'solve')):
    job = IsolatedProcedure(['A'], state_file, [Step(session, 'solve', fails)], session)
    assert job.act() == job.FAILURE and job.failed.label == label, job.failed
    assert 'recovery data' in job.error and ('solve failed' in job.error) == fails, job.error
    assert not json.loads(state_file.read_text())['restored']
''')

    def test_root_analysis_selects_critical_parts_once_and_swaps_boards(self):
        self.run_isolated(ROOT_ANALYSIS + r'''
sections.write_text('board = BoardA Sphere_positions = 399 258\nboard = BoardA Sphere_positions = 1 2\n'
                    'board = BoardB Sphere_positions = 3 4\nboard = BoardA Sphere_positions = 5 6\n')
job = RootAnalysis(session, settings, options, run_dir)
assert [case.label for case in job.cases][::3] == ['case_1_VCC399_GND258', 'case_4_VCC5_GND6']
assert selected == [] and app.validate_simple.call_count == 0  # nothing changed before running
results = job.run()
assert selected == ['Region', 'GND', 'VCC', 'Sphere_GND', 'Sphere_VCC', 'BoardA', 'BoardB', 'BoardA'], selected
assert [inactive for inactive, _ in seen] == [['BoardB', 'C', 'Other'], ['BoardB', 'C', 'Other'],
                                              ['BoardA', 'C', 'Other'], ['BoardB', 'C', 'Other']], seen
assert seen[0][1] == {'PinCount': '399', 'PinCountGND': '258'}, seen
assert [r['board'] for r in results] == ['BoardA', 'BoardA', 'BoardB', 'BoardA'], results
assert all(r['status'] == 'success' and r['Bz max (T)'] == 0.004 for r in results), results
assert groups['Non Model'] == ['C'] and values == {'PinCount': '7', 'PinCountGND': '8'}, (groups, values)
assert json.loads((run_dir / 'original_state.json').read_text())['restored']
assert app.save_project.call_count == 1
''')

    def test_root_analysis_stops_at_a_failed_case_and_restores_once(self):
        self.run_isolated(ROOT_ANALYSIS + r'''
sections.write_text('board = BoardA Sphere_positions = 399 258\nboard = BoardB Sphere_positions = 1 2\n'
                    'board = BoardA Sphere_positions = 3 4\n')
verdicts[:] = [1, 0]
job = RootAnalysis(session, settings, options, run_dir)
try:
    job.run()
    raise AssertionError('no ActionFailed')
except ActionFailed as e:
    assert str(e).startswith('case_2_VCC1_GND2 failed: AEDT validation check failed'), e
first, second = job.result
assert first['status'] == 'success', first
assert second['status'] == 'failed' and second['error'].startswith('Check_validity: '), second
result = json.loads((run_dir / 'case_2_VCC1_GND2/result.json').read_text())
assert result['status'] == 'failed', result
assert len(seen) == 2 and groups['Non Model'] == ['C'], (seen, groups)
assert values == {'PinCount': '7', 'PinCountGND': '8'} and app.save_project.call_count == 1, values
''')

    def test_root_analysis_refuses_a_row_with_other_critical_parts(self):
        self.run_isolated(ROOT_ANALYSIS + r'''
sections.write_text('board,vcc_pin,gnd_pin,vcc\nBoardA,1,2,\nBoardA,3,4,Other\n')
try:
    RootAnalysis(session, settings, options, run_dir)
    raise AssertionError('no LookupError')
except LookupError as e:
    assert 'line 3' in str(e) and 'Other' in str(e), e
assert selected == [] and groups['Non Model'] == ['C'], groups
''')

    def test_bz_procedure_solves_and_exports_through_the_session(self):
        self.run_isolated(r'''
import tempfile
from AnsysSession.Action.AnalysisActions.BzProcedure import BzProcedure
app.setup_names = ['Setup1']
app.analyze_setup.return_value = True
app.design_name, app.project_name = 'D1', 'P'
app.modeler.model_units = 'mm'
app.existing_analysis_sweeps = ['Setup1 : LastAdaptive']
app.variable_manager.independent_design_variables = {'w': Mock(expression='2mm')}
reporter = app.ofieldsreporter
reporter.DoesNamedExpressionExists.return_value = False
def write_grid(path, *arguments):
    with open(path, 'w') as stream:
        stream.write('x y z Bz\n' + '0 0 1 0.001\n1 0 1 0.002\n0 1 1 0.003\n1 1 1 0.004\n' * 5)
reporter.ExportOnGrid.side_effect = write_grid
board = Mock(bounding_box=[0, 0, 0, 1, 1, 1])
result = BzProcedure(session, board, output_dir=tempfile.mkdtemp(), step=0.5).run()
app.analyze_setup.assert_called_once_with('Setup1', cores=None)
reporter.AddNamedExpression.assert_called_once()
arguments = reporter.ExportOnGrid.call_args.args
assert arguments[0].endswith('P_D1_Setup1_Bz.fld') and arguments[1][:2] == ['0mm', '0mm'], arguments
assert arguments[4] == 'Setup1 : LastAdaptive' and arguments[5] == ['w:=', ['2mm']], arguments
assert result['solution'] == 'Setup1 : LastAdaptive' and result['Bz max (T)'] == 0.004, result
''')

    def test_correct_ground_offset_reads_and_edits_through_the_session(self):
        self.run_isolated(r'''
from AnsysSession.Action.CorrectGroundOffset import CorrectGroundOffset, NEW_X, OLD_X
vectors = {'GND': [OLD_X, '0', '0'], 'Sphere_GND': [OLD_X, '1', '0']}
class Node:
    def __init__(self, name):
        self.name = name
    def GetChildNames(self):
        return ['Rotate:1', 'Move:1']
    def GetChildObject(self, operation):
        return self
    def GetPropValue(self, path):
        return vectors[self.name]['XYZ'.index(path[-1])]
def change_vector(arguments):
    tab = arguments[1]
    vectors[tab[1][1].split(':')[0]] = tab[2][1][2::2]
native.GetChildObject.side_effect = Node
native.ChangeProperty.side_effect = change_vector
result = CorrectGroundOffset(session).run()
assert vectors == {'GND': [NEW_X, '0', '0'], 'Sphere_GND': [NEW_X, '1', '0']}, vectors
assert result['x_expression'] == NEW_X
''')


if __name__ == '__main__':
    unittest.main()
