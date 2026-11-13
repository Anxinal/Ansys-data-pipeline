from ...KeepSession import keep_session_on_error
from ..Action import AnsysProcedure
from .BackgroundSelect import BackgroundSelect
from .RestoreState import RestoreState
from .SelectForAnalysis import DeselectAll


class IsolatedProcedure(AnsysProcedure):
    """Run ``steps`` with preserved parts and background active; select other parts as needed.

    ``selected`` names the objects they will use, which must exist. The original state always comes back.
    """

    def __init__(self, selected, state_file, steps, session, label="isolated", preserve=()):
        deselect = DeselectAll(session, selected, state_file, preserve)
        super().__init__([deselect, BackgroundSelect(session, deselect), *steps], session, label)
        self.restore = RestoreState(session, state_file)

    def act(self):
        state_file = self.restore.state_file
        state_file.unlink(missing_ok=True)  # so an earlier run's state is never restored
        with keep_session_on_error():
            status = super().act()
            # No file: the selection was refused before anything changed.
            restored = self.restore.act() if state_file.exists() else self.SUCCESS
        if restored != self.SUCCESS:
            self.failed = self.failed or self.restore
            self.error = "; ".join(filter(None, (self.error, self.restore.error)))
        return status or restored
