from Chips import Chip
from Chips.Generators import FileSectionGenerator

from ..Action import AnsysAction


class RootCandidates(AnsysAction):
    """The SectionCandidates of settings.SECTIONS_FILE; ``names`` holds every object their cases use.

    Only the critical parts and the listed boards are read: the critical parts are selected
    once for all cases, so a row naming other terminals or spheres fails here.
    """

    def __init__(self, session, settings):
        super().__init__(session, "Root_Candidates")
        self.settings = settings
        self.names = []

    def act(self):
        settings = self.settings
        boards = [row["board"] for _, row in FileSectionGenerator.read_rows(settings.SECTIONS_FILE)]
        self.names = sorted({settings.DEFAULT_GND, settings.DEFAULT_VCC, *settings.DEFAULT_SPEHRE, *boards})
        chip = Chip(self.session.selected_components(self.names), gnd=settings.DEFAULT_GND, vcc=settings.DEFAULT_VCC,
                    spheres=settings.DEFAULT_SPEHRE, boards=list(dict.fromkeys(boards)), units=self.session.units)
        self.result = list(FileSectionGenerator(chip, settings.SECTIONS_FILE))
        return self.SUCCESS
