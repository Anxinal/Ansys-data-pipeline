"""Copy one board section of the main chip, place its terminals by pin count, then validate, solve and export.

Typical loop over a generator's candidates (run SwitchBackToMain between copies):

    chip = Chip(original_components(session.snapshot), units=session.snapshot.units)
    for candidate in FileSectionGenerator(chip, "sections.csv"):
        job = CopyandGenerate(session, candidate, cores=8)
        if job.act() != job.SUCCESS:
            print(f"{job.failed.label} failed: {job.error}")
        SwitchBackToMain(session, job.main_design).act()
"""

from Chips.Generators import SectionCandidate
from configs import DEFAULT_GRID_STEP, DEFAULT_OUTPUT_DIR, DEFAULT_PREFIX, DEFAULT_SCAN_HEIGHT, DEFAULT_SETUP

from ..ModelEditor import AedtError
from ..SwitchDesign import copy_chip, switch_to_copy
from .Action import AnsysProcedure
from .BzProcedure import BzProcedure
from .CheckValidity import CheckValidity
from .ExtractCopy import ExtractCopy
from .SetTerminalPositions import SetTerminalPositions


class CopyandGenerate(AnsysProcedure):
    """Copy a candidate's chip section and generate its Bz data; ``result`` is the export summary.

    session     the open Session, with the main design active
    candidate   a SectionCandidate (e.g. from a FeasibleChipSectionGenerator): the
                ChipSection to copy and the pair its VCC (a) and GND (b) go to

    The section's board, two spheres and GND/VCC are copied in place into the next
    "<prefix><n>" group (ExtractCopy). In the copy's analysis design, where only
    that copy remains, the pin-count variables are set from the pair
    (SetTerminalPositions: PinCount for VCC, PinCountGND for GND), which moves
    each terminal with its sphere. Then the design is validated (CheckValidity),
    solved and exported at those values (BzProcedure) and the project saved.
    The analysis design is left active: SwitchBackToMain returns to
    ``main_design``.
    """

    def __init__(self, session, candidate: SectionCandidate, setup=DEFAULT_SETUP, output_dir=DEFAULT_OUTPUT_DIR,
                 scan_height=DEFAULT_SCAN_HEIGHT, step=DEFAULT_GRID_STEP, cores=None, solve=True,
                 prefix=DEFAULT_PREFIX):
        super().__init__([], session.app, "Copy_and_Generate")  # the steps after the copy need the copy
        self.session = session
        self.section = candidate.section
        self.pair = candidate.pair
        self.bz_options = dict(setup=setup, output_dir=output_dir, scan_height=scan_height, step=step,
                               cores=cores, solve=solve)
        self.prefix = prefix
        self.main_design = None
        self.result = None

    def act(self):
        session = self.session
        self.main_design = session.design
        extraction = ExtractCopy(self.app, session.snapshot, self.section, positions={}, prefix=self.prefix)
        self.actions = [extraction]
        status = super().act()
        session.refresh()
        if status != self.SUCCESS:
            return status

        try:
            design, group = switch_to_copy(session, extraction.result.group, self.main_design)
            copy = copy_chip(session, group, self.main_design)
            bz = BzProcedure(self.app, copy.board, **self.bz_options)  # checks the setup exists
        except (AedtError, LookupError, ValueError) as e:
            # Not one of the steps: report this procedure as the failed one.
            self.failed, self.error = self, f"{type(e).__name__}: {e}"
            return self.FAILURE

        self.actions = [SetTerminalPositions(self.app, copy, self.pair), CheckValidity(self.app), bz]
        status = super().act()
        session.refresh()
        if status != self.SUCCESS:
            return status

        session.save()
        self.result = {"design": design, "group": group,
                       "VCC pin count": copy.vcc.position_value, "GND pin count": copy.gnd.position_value,
                       "VCC": str(self.pair.a), "GND": str(self.pair.b), **bz.result}
        return self.SUCCESS
