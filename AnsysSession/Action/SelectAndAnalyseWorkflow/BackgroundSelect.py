from .SelectForAnalysis import BoardSelect


class BackgroundSelect(BoardSelect):
    """Make the background objects that ``deselect`` (a DeselectAll) turned off active again."""

    def __init__(self, session, deselect):
        super().__init__(session, [], "Background_Select")
        self.deselect = deselect

    def act(self):
        self.set_components(self.session.selected_components(self.deselect.result["background"]))
        return super().act()
