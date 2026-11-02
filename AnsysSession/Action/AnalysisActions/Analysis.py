"""The analyse step: solve a setup of the active design (saving is left to the caller)."""

from configs import DEFAULT_SETUP

from ..Action import AnsysAction


class BzAnalysis(AnsysAction):
    """Solve the setup in the active design. Save the project afterwards to keep the solution."""

    def __init__(self, session, setup=DEFAULT_SETUP, cores=None):
        super().__init__(session, "Analyse_Bz")
        if setup not in session.setup_names:
            raise ValueError(f'No setup "{setup}" in design "{session.design}". Available: {session.setup_names}')
        self.setup = setup
        self.cores = cores

    def act(self):
        print(f'Solving "{self.setup}" in design "{self.session.design}"...')
        if not self.session.solve(self.setup, self.cores):
            self.error = f'AEDT failed to solve "{self.setup}". See the AEDT message manager for details.'
            return self.FAILURE
        return self.SUCCESS
