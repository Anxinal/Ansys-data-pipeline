"""Run selected source sections in place without copying or duplicating designs."""

from pathlib import Path

from .IsolatedProcedure import IsolatedProcedure
from .RootCandidates import RootCandidates
from .RootCase import RootCase
from .SelectForAnalysis import SelectNecessaryComponents


class RootAnalysis(IsolatedProcedure):
    """A RootCase per row of settings.SECTIONS_FILE, in folders under ``run_dir``; ``result`` lists their results.

    Every row is checked here, before anything changes. The critical parts are selected once, each
    case only swaps the board, and the project is saved after the original state is back, so a
    crash never saves the isolated state. <run_dir>/original_state.json records the restoration.
    """

    def __init__(self, session, settings, bz_options, run_dir):
        candidates = RootCandidates(session, settings)
        self.cases, previous = [], None
        for index, candidate in enumerate(candidates.run(), 1):
            folder = f"case_{index}_VCC{candidate.pair.a.value}_GND{candidate.pair.b.value}"
            self.cases.append(RootCase(session, candidate, bz_options, Path(run_dir) / folder, previous))
            previous = candidate.section.board
        steps = [SelectNecessaryComponents(session), *self.cases]
        super().__init__(candidates.names, Path(run_dir) / "original_state.json", steps, session, "Root_Analysis")

    def act(self):
        status = super().act()
        self.result = [case.result for case in self.cases if case.result]
        if self.restore.result and self.restore.result["restored"]:
            self.session.save()
        return status
