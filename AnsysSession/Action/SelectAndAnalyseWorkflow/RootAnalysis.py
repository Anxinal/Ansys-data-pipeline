"""Run selected source sections in place without copying or duplicating designs."""

import json
from pathlib import Path

from .IsolatedProcedure import IsolatedProcedure
from .RootCandidates import RootCandidates
from .RootCase import RootCase
from .SelectForAnalysis import SelectNecessaryComponents


class RootAnalysis(IsolatedProcedure):
    """A RootCase per generated combination under ``run_dir``; ``result`` lists their results.

    Every row is checked here, before anything changes. The critical parts are selected once, each
    case only swaps the board, and the project is saved after the original state is back, so a
    workflow saves only restored state. <run_dir>/original_state.json records the restoration.
    """

    def __init__(self, session, settings, bz_options, run_dir, procedure=None):
        candidates = RootCandidates(session, settings)
        self.cases, previous = [], None
        for index, candidate in enumerate(candidates.run(), 1):
            folder = f"case_{index}_VCC{candidate.pair.a.value}_GND{candidate.pair.b.value}"
            options = {'procedure':procedure} if procedure is not None else {}
            self.cases.append(RootCase(session, candidate, bz_options, Path(run_dir) / folder, previous, **options))
            previous = candidate.section.board
        steps = [SelectNecessaryComponents(session), *self.cases]
        preserve = [settings.DEFAULT_GND, settings.DEFAULT_VCC, *settings.DEFAULT_SPEHRE]
        super().__init__(candidates.names, Path(run_dir) / "original_state.json", steps, session,
                         "Root_Analysis", preserve=preserve)
        Path(run_dir).mkdir(parents=True, exist_ok=True)
        (Path(run_dir)/'candidates.json').write_text(json.dumps([c.summary for c in self.cases], indent=2))

    def act(self):
        print(f'Running {len(self.cases)} root-selection cases', flush=True)
        status = super().act()
        self.result = [case.result for case in self.cases if case.result]
        if self.restore.result and self.restore.result["restored"]:
            self.session.save()
        return status
