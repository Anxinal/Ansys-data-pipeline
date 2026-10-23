from ..ModelEditor import AedtError
from .Action import AnsysAction


class SwitchBackToMain(AnsysAction):
    """Make the main design active again (e.g. CopyandGenerate.main_design), so the next copy can be made.

    Switching through the session also re-reads its snapshot, so the next
    ExtractCopy sees the copies made so far and picks the next free group name.
    """

    def __init__(self, session, main_design):
        super().__init__(session.app, "Switch_Back_To_Main")
        self.session = session
        self.main_design = main_design

    def act(self):
        if not self.main_design:
            self.error = "No main design to switch back to"
            return self.FAILURE
        try:
            self.session.switch_design(self.main_design)
        except AedtError as e:
            self.error = str(e)
            return self.FAILURE
        return self.SUCCESS
