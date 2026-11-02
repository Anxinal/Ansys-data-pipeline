from Chips.Components import Component

from .Action import AnsysAction


class GenerateSnapshot(AnsysAction):
    """Take a top-view picture of ``component`` (usually a board); ``result`` is its BoardImage.

    See Session.obtain_image_snapshot: AEDT must run in graphical mode and
    configs.GRID_SIZE must be set.
    """

    def __init__(self, session, component: Component):
        super().__init__(session, "Generate_Snapshot")
        self.component = component

    def act(self) -> int:
        try:
            self.result = self.session.obtain_image_snapshot(self.component)
        except (RuntimeError, ValueError) as e:
            self.error = f'{e} (component "{self.component.name}")'
            return self.FAILURE
        return self.SUCCESS
