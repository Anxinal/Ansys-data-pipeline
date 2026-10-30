"""Copy one board section of the main chip, place its terminals by pin count, then validate, solve and export.

Typical loop over a generator's candidates (run SwitchBackToMain between copies):

    chip = Chip(original_components(session.snapshot), units=session.snapshot.units)
    for candidate in FileSectionGenerator(chip, "sections.csv"):
        job = CopyandGenerate(session, candidate, cores=8)
        if job.act() != job.SUCCESS:
            print(f"{job.failed.label} failed: {job.error}")
        SwitchBackToMain(session, job.main_design).act()
"""

from dataclasses import replace

from Chips.Generators import SectionCandidate
from configs import DEFAULT_GRID_STEP, DEFAULT_OUTPUT_DIR, DEFAULT_PREFIX, DEFAULT_SCAN_HEIGHT, DEFAULT_SETUP

from ..ModelEditor import AedtError
from ..CopyStore import CopyStore
from ..SwitchDesign import copy_chip, switch_to_copy
from .Action import AnsysAction, AnsysProcedure
from .BzProcedure import BzProcedure
from .CheckValidity import CheckValidity
from .ExtractCopy import ExtractCopy
from .PurgeHistory import PurgeHistory
from .SetTerminalPositions import SetTerminalPositions


class CopyandGenerate(AnsysAction):
    """Copy a candidate's chip section and generate its Bz data; ``result`` is the export summary.

    session     the open Session, with the main design active
    candidate   a SectionCandidate (e.g. from a FeasibleChipSectionGenerator): the
                ChipSection to copy and the pair its VCC (a) and GND (b) go to

    The section's board, two spheres and GND/VCC are copied in place into the next
    "<prefix><n>" group (ExtractCopy). In the copy's analysis design, where only
    that copy remains, the pin-count variables are set from the pair
    (SetTerminalPositions: PinCount for VCC, PinCountGND for GND). Only geometry
    driven by those expressions follows them; spheres are not explicitly moved.
    Then the design is validated (CheckValidity),
    solved and exported at those values (BzProcedure) and the project saved.
    The analysis design is left active: SwitchBackToMain returns to
    ``main_design``.

    With extract_only=True, copy only the five selected objects in the source
    design and record the requested pins as metadata. Do not duplicate a design
    or change its global pin variables. Geometry stays in place.

    On failure, ``failed`` is the step that failed (or this action itself when
    the copy's analysis design can't be set up).
    """

    def __init__(self, session, candidate: SectionCandidate, setup=DEFAULT_SETUP, output_dir=DEFAULT_OUTPUT_DIR,
                 scan_height=DEFAULT_SCAN_HEIGHT, step=DEFAULT_GRID_STEP, cores=None, solve=True,
                 prefix=DEFAULT_PREFIX, extract_only=False, purge_history=False):
        super().__init__(session.app, "Copy_and_Generate")
        self.session = session
        self.section = candidate.section
        self.pair = candidate.pair
        self.bz_options = dict(setup=setup, output_dir=output_dir, scan_height=scan_height, step=step,
                               cores=cores, solve=solve)
        self.prefix = prefix
        self.extract_only = extract_only
        self.purge_history = purge_history
        self.main_design = None
        self.failed = None

    def act(self):
        self.main_design = self.session.design
        extraction = ExtractCopy(self.app, self.session.snapshot, self.section, positions={}, prefix=self.prefix)
        status = self._steps([extraction])
        if status != self.SUCCESS:
            return status
        return self._record_only(extraction) if self.extract_only else self._analyse(extraction)

    def _steps(self, actions):
        """Run ``actions`` in order, then re-read the session; on failure, keep which step failed."""
        procedure = AnsysProcedure(actions, self.app, self.label)
        status = procedure.act()
        self.session.refresh()
        if status != self.SUCCESS:
            self.failed, self.error = procedure.failed, procedure.error
        return status

    def _purge_steps(self, extraction):
        return [PurgeHistory(self.app, list(extraction.result.copies.values()))] if self.purge_history else []

    def _save_record(self, record):
        """Save the project, then the copy's record; returns where the record is kept."""
        self.session.save()
        store = CopyStore(self.app)
        store.save(record)
        return str(store.path)

    def _record_only(self, extraction):
        """extract_only: optionally purge the copies, then record the requested pins without placing them."""
        status = self._steps(self._purge_steps(extraction))
        if status != self.SUCCESS:
            return status
        record = replace(extraction.result, pin_counts={"VCC": self.pair.a.value, "GND": self.pair.b.value})
        self.result = {"design": self.main_design, "group": record.group,
                       "copies": record.copies,
                       "requested VCC pin count": self.pair.a.value,
                       "requested GND pin count": self.pair.b.value,
                       "placement": "copied in place; requested pins recorded as metadata",
                       "history purged": self.purge_history,
                       "copy record": self._save_record(record)}
        return self.SUCCESS

    def _analyse(self, extraction):
        """Switch to the copy's analysis design, place its terminals, validate, solve and export."""
        try:
            design, group = switch_to_copy(self.session, extraction.result.group, self.main_design)
            copy = copy_chip(self.session, group, self.main_design)
            bz = BzProcedure(self.app, copy.board, **self.bz_options)
        except (AedtError, LookupError, ValueError) as e:
            # Not one of the steps: report this action as the failed one.
            self.failed, self.error = self, f"{type(e).__name__}: {e}"
            return self.FAILURE

        steps = [SetTerminalPositions(self.app, copy, self.pair), *self._purge_steps(extraction),
                 CheckValidity(self.app), bz]
        status = self._steps(steps)
        if status != self.SUCCESS:
            return status

        record = replace(extraction.result, pin_counts={"VCC": self.pair.a.value, "GND": self.pair.b.value},
                         analysis_design=design)
        self.result = {"design": design, "group": group,
                       "VCC pin count": copy.vcc.position_value, "GND pin count": copy.gnd.position_value,
                       "VCC": str(self.pair.a), "GND": str(self.pair.b),
                       "sphere placement": "not explicitly moved; depends on project expressions",
                       "history purged": self.purge_history,
                       "copy record": self._save_record(record),
                       **bz.result}
        return self.SUCCESS
