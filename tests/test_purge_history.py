"""Purge selection guards and workflow ordering, without modifying a live project."""
import subprocess
import sys
import unittest


IMPORTS = r'''
import importlib
import sys
import types
from unittest.mock import Mock, patch
reader = types.ModuleType('AnsysSession.DesignReader')
reader.DesignReader = Mock()
sys.modules[reader.__name__] = reader
'''


class PurgeHistoryTests(unittest.TestCase):
    def run_isolated(self, code):
        result = subprocess.run([sys.executable, '-B', '-c', IMPORTS + code],
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_explicit_selection_and_backend_failure(self):
        self.run_isolated(r'''
from AnsysSession.Action.PurgeHistory import PurgeHistory
app = Mock()
names = ['BOARD_1_board', 'BOARD_1_s1', 'BOARD_1_s2', 'BOARD_1_vcc', 'BOARD_1_gnd']
app.modeler.get_object_from_name.side_effect = lambda name: object() if name in names else None
app.modeler.purge_history.return_value = True
action = PurgeHistory(app, names)
assert action.act() == action.SUCCESS
app.modeler.purge_history.assert_called_once_with(assignment=names)
app.save_project.assert_not_called()
for invalid in ([], [''], ['BOARD_1_board', 'missing']):
    app.modeler.purge_history.reset_mock()
    action = PurgeHistory(app, invalid)
    assert action.act() == action.FAILURE
    assert action.error
    app.modeler.purge_history.assert_not_called()
app.modeler.purge_history.return_value = False
assert PurgeHistory(app, names).act() == 1
app.modeler.purge_history.side_effect = RuntimeError('AEDT refused')
action = PurgeHistory(app, names)
assert action.act() == 1 and 'AEDT refused' in action.error
''')

    def test_generating_places_before_purging_and_skips_purge_by_default(self):
        self.run_isolated(r'''
from pathlib import Path
sys.path.insert(0, str(Path('tests').resolve()))
from test_chips import chip_components
from Chips import ChipSection, CopyRecord, NumericalPositionFixed, TerminalPositionPair
from Chips.Generators import SectionCandidate
workflow = importlib.import_module('AnsysSession.Action.CopyandGenerate')
section = ChipSection(chip_components())
pair = TerminalPositionPair(NumericalPositionFixed.from_number(399, z=1.2),
                            NumericalPositionFixed.from_number(258, z=1.2))
candidate = SectionCandidate(section, pair)
names = ['BOARD_1_board','BOARD_1_s1','BOARD_1_s2','BOARD_1_vcc','BOARD_1_gnd']
record = CopyRecord('BOARD_1', 'D1', copies=dict(zip(['board','s1','s2','vcc','gnd'],names)))
for enabled in (False, True):
    events = []
    def action(label):
        step = Mock()
        step.act.side_effect = lambda: (events.append(label) or 0)
        return step
    extraction = action('extract')
    extraction.result = record
    session = Mock(design='D1')
    session.save.side_effect = lambda: events.append('save')
    store = Mock(path=Path('copies.json'))
    store.save.side_effect = lambda value: events.append('record')
    bz = action('bz')
    bz.result = {}
    with patch.object(workflow, 'ExtractCopy', return_value=extraction), \
         patch.object(workflow, 'switch_to_copy', return_value=('D1_BOARD_1','BOARD_1')), \
         patch.object(workflow, 'copy_chip', return_value=section), \
         patch.object(workflow, 'SetTerminalPositions', return_value=action('place')), \
         patch.object(workflow, 'PurgeHistory', return_value=action('purge')) as purge, \
         patch.object(workflow, 'CheckValidity', return_value=action('validate')), \
         patch.object(workflow, 'BzProcedure', return_value=bz), \
         patch.object(workflow, 'CopyStore', return_value=store):
        job = workflow.CopyandGenerate(session, candidate, purge_history=enabled)
        assert job.act() == 0, job.error
        expected = ['extract','place'] + (['purge'] if enabled else []) + ['validate','bz','save','record']
        assert events == expected, events
        if enabled:
            purge.assert_called_once_with(session.app, names)
        else:
            purge.assert_not_called()
''')


if __name__ == '__main__':
    unittest.main()
