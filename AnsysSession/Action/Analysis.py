"""The analyse step: solve a setup of the active design (saving is left to the caller)."""

from configs import DEFAULT_SETUP

from .Action import AnsysAction


def solution_name(app, setup):
    """The setup's solution, e.g. "Setup1 : LastAdaptive"."""
    for solution in app.existing_analysis_sweeps:
        if solution.split(":")[0].strip() == setup:
            return solution
    return f"{setup} : LastAdaptive"


class BzAnalysis(AnsysAction):
    """Solve the setup in the active design. Save the project afterwards to keep the solution."""

    def __init__(self, app, setup=DEFAULT_SETUP, cores=None):
        super().__init__(app, "Analyse_Bz")
        if setup not in app.setup_names:
            raise ValueError(f'No setup "{setup}" in design "{app.design_name}". Available: {app.setup_names}')
        self.setup = setup
        self.cores = cores

    def act(self):
        print(f'Solving "{self.setup}" in design "{self.app.design_name}"...')
        if not self.app.analyze_setup(self.setup, cores=self.cores):
            self.error = f'AEDT failed to solve "{self.setup}". See the AEDT message manager for details.'
            return self.FAILURE
        return self.SUCCESS
