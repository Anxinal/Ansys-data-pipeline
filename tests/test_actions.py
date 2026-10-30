"""The action base class (run(), result) and GenerateSnapshot, on fake AEDT apps; no AEDT needed."""
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

class Post:
    def __init__(self, draw):
        self.draw = draw
    def export_model_picture(self, full_name, **options):
        assert options['orientation'] == 'top' and options['selections'] == ['Board'], options
        if self.draw:  # gradient background with a 75 x 40 board at (30, 20)
            pixels = np.linspace(200, 255, 120)[:, None, None] * np.ones((1, 160, 3))
            pixels[20:60, 30:105] = [40, 120, 40]
            Image.fromarray(pixels.astype(np.uint8)).save(full_name, quality=90)
        return str(full_name)

folder = tempfile.mkdtemp()
app = Mock(working_directory=folder, design_name='Maxwell 3D: copy', post=Post(True))
board = Mock()
board.name = 'Board'
design_reader.GRID_SIZE = [10, 10]
image = GenerateSnapshot(app, board).run()
assert image.image.size == (75, 40), image.image.size
assert (image.name, len(image.split_all())) == ('Board', 7 * 4)

app.post = Post(False)
action = GenerateSnapshot(app, board)
assert action.act() == action.FAILURE and 'graphical mode' in action.error, action.error
design_reader.GRID_SIZE = []
action = GenerateSnapshot(app, board)
assert action.act() == action.FAILURE and 'GRID_SIZE' in action.error, action.error
''')


if __name__ == '__main__':
    unittest.main()
