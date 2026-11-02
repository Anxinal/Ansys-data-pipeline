from abc import ABC, abstractmethod


class ActionFailed(RuntimeError):
    """An action (or a step of a procedure) returned a non-zero status from run()."""


class AnsysAction(ABC):
    """One step performed on a Session's active design.

    Every read and change goes through ``self.session``, the only way into AEDT.
    An action that produces something leaves it in ``self.result``.
    """

    SUCCESS = 0
    FAILURE = 1

    def __init__(self, session, label="actionx"):
        self.session = session
        self.label = label
        self.error = None  # what went wrong when act() returns a non-zero status
        self.result = None  # what act() produced, if anything

    @abstractmethod
    def act(self) -> int:
        """Perform the action and return its exit status (SUCCESS, or non-zero on failure)."""

    def run(self):
        """act(), then ``self.result``; raises ActionFailed naming the failed step instead of returning a status."""
        if self.act() != self.SUCCESS:
            failed = getattr(self, "failed", None) or self
            raise ActionFailed(f"{failed.label} failed: {self.error}")
        return self.result

    def save_changes(self):
        """Save the project; returns SUCCESS or FAILURE."""
        try:
            self.session.save()
        except RuntimeError as e:
            self.error = str(e)
            return self.FAILURE
        return self.SUCCESS


class AnsysProcedure(AnsysAction):
    """Actions on the same Session that must run in order; stops at the first failure."""

    def __init__(self, actions, session, label="procedure"):
        super().__init__(session, label)
        self.actions = list(actions)
        self.failed = None  # the action that failed, if any

    def act(self):
        for action in self.actions:
            try:
                status = action.act()
            except Exception as e:  # e.g. an AedtError inside the step: record which step failed
                action.error = f"{type(e).__name__}: {e}"
                status = self.FAILURE
            if status != self.SUCCESS:
                self.failed, self.error = action, action.error
                return status
        return self.SUCCESS
