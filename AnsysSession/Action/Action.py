from abc import ABC, abstractmethod

from ..DesignReader import DesignReader
from ..ModelEditor import ModelEditor


class AnsysAction(ABC):
    """One step performed within an app design. Switching design is done outside of this class,
    except by CopyAndGenerate and SwitchBackToMain, which hold the Session for it.

    Changes to the design go through ``self.editor`` (ModelEditor), reads through
    ``self.reader`` (DesignReader).
    """

    SUCCESS = 0
    FAILURE = 1

    def __init__(self, app, label="actionx"):
        self.app = app
        self.label = label
        self.error = None  # what went wrong when act() returns a non-zero status
        self.log = None

    @abstractmethod
    def act(self) -> int:
        """Perform the action and return its exit status (SUCCESS, or non-zero on failure)."""

    @property
    def editor(self):
        return ModelEditor(self.app)

    @property
    def reader(self):
        return DesignReader(self.app)

    def get_attribute(self, attr):
        """An attribute of the app, e.g. "design_name"."""
        return getattr(self.app, attr)

    def update_attribute(self, attr, value):
        """Set an attribute of the app and return the value read back."""
        setattr(self.app, attr, value)
        return getattr(self.app, attr)

    def get_attribute_recursive(self, path, obj=None):
        """A nested attribute of the app, by its path, e.g. ["modeler", "model_units"]."""
        obj = self.app if obj is None else obj
        if not path:
            return obj
        if not hasattr(obj, path[0]):
            raise AttributeError(f"{type(obj).__name__} has no attribute {path[0]!r}")
        return self.get_attribute_recursive(path[1:], getattr(obj, path[0]))

    def update_attribute_recursive(self, path, value):
        """Set a nested attribute of the app by its path and return the value read back."""
        if not path:
            raise ValueError("update_attribute_recursive needs a non-empty path")
        try:
            parent = self.get_attribute_recursive(path[:-1])
        except AttributeError as e:
            raise AttributeError(f"Cannot reach {'.'.join(path)}: {e}") from None
        setattr(parent, path[-1], value)
        return getattr(parent, path[-1])

    def save_changes(self):
        """Save the project; returns SUCCESS or FAILURE."""
        try:
            self.editor.save()
        except RuntimeError as e:
            self.error = str(e)
            return self.FAILURE
        return self.SUCCESS

    def print_log(self):
        print(self.log)


class AnsysReturnableAction(AnsysAction):

    def __init__(self, app, label="actionx"):
        super().__init__(app, label)
        self.result = None
        self.isexecuted = False

    @abstractmethod
    def act(self):
        """return the result of action at the end"""
        pass

    def return_result(self):
        """The action's result, running act() first if it hasn't run yet."""
        if not self.isexecuted:
            self.act()
            self.isexecuted = True
        return self.result



class AnsysProcedure(AnsysAction):
    """Actions within the same app that must run in order; stops at the first failure."""

    def __init__(self, actions, app, label="procedure"):
        super().__init__(app, label)
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
