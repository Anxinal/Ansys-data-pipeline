"""Optional removal of modeling history from an explicit set of objects."""

from ..ModelEditor import AedtError
from .Action import AnsysAction


class PurgeHistory(AnsysAction):
    """Freeze the selected objects' current geometry by purging their history.

    Call after any expression-driven placement: those history expressions no
    longer reposition a purged object. No save is performed by this action.
    Refresh the session snapshot after running it.
    """

    def __init__(self, session, names):
        super().__init__(session, "Purge_History")
        self.names = [names] if isinstance(names, str) else list(names)

    def act(self):
        self.error = None
        try:
            self.session.purge_history(self.names)
        except (AedtError, ValueError) as e:
            self.error = str(e)
            return self.FAILURE
        return self.SUCCESS
