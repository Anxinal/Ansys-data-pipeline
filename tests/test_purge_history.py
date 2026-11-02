"""Purge selection guards and workflow ordering, without modifying a live project."""
import subprocess
import sys
import unittest


IMPORTS = r'''
import importlib
import sys
import types
from unittest.mock import Mock, patch
'''


class PurgeHistoryTests(unittest.TestCase):
    def run_isolated(self, code):
        result = subprocess.run([sys.executable, '-B', '-c', IMPORTS + code],
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_explicit_selection_and_backend_failure(self):
        self.run_isolated(r'''
from AnsysSession.Action.PurgeHistory import PurgeHistory
from AnsysSession.ModelEditor import ModelEditor
app = Mock()
session = Mock()
session.purge_history = ModelEditor(app).purge_history
names = ['BOARD_1_board', 'BOARD_1_s1', 'BOARD_1_s2', 'BOARD_1_vcc', 'BOARD_1_gnd']
app.modeler.get_object_from_name.side_effect = lambda name: object() if name in names else None
app.modeler.purge_history.return_value = True
action = PurgeHistory(session, names)
assert action.act() == action.SUCCESS
app.modeler.purge_history.assert_called_once_with(assignment=names)
app.save_project.assert_not_called()
for invalid in ([], [''], ['BOARD_1_board', 'missing']):
    app.modeler.purge_history.reset_mock()
    action = PurgeHistory(session, invalid)
    assert action.act() == action.FAILURE
    assert action.error
    app.modeler.purge_history.assert_not_called()
app.modeler.purge_history.return_value = False
assert PurgeHistory(session, names).act() == 1
app.modeler.purge_history.side_effect = RuntimeError('AEDT refused')
action = PurgeHistory(session, names)
assert action.act() == 1 and 'AEDT refused' in action.error
''')


if __name__ == '__main__':
    unittest.main()
