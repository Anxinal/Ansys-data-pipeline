"""Open or reuse only the project and design explicitly configured for a run."""
from pathlib import Path

from ansys.aedt.core import Desktop, get_pyaedt_app
from .ExistingSession import connect_existing
from .GrpcCompatibility import local_grpc_metadata, local_grpc_port_detection
from .ProjectLock import existing_project_port
from .Session import Session


def open_configured(settings, output):
    expected = Path(settings.DEFAULT_INPUT_PATH).resolve(strict=True)
    port = existing_project_port(expected, output)
    with local_grpc_metadata(), local_grpc_port_detection(port):
        desktop = connect_existing(port, non_graphical=not settings.SHOW_DESKTOP) if port else Desktop(
            version='2025.1', new_desktop=True, non_graphical=not settings.SHOW_DESKTOP, close_on_exit=False)
        try:
            project = desktop.odesktop.GetActiveProject()
            if not project:
                project = desktop.odesktop.OpenProject(str(expected))
            actual = (Path(project.GetPath())/(project.GetName()+'.aedt')).resolve()
            if actual != expected:
                raise RuntimeError(f'Refusing unexpected project {actual}; expected {expected}')
            if settings.SHOW_DESKTOP:
                if desktop.odesktop.GetIsNonGraphical():
                    raise RuntimeError('The configured project is open in a headless AEDT session. '
                                       'Close that session, then rerun this file to open the GUI.')
                desktop.odesktop.RestoreWindow()
            project.SetActiveDesign(settings.DESIGN)
            app = get_pyaedt_app(project.GetName(), settings.DESIGN, desktop=desktop)
            if not app or app.design_name != settings.DESIGN:
                raise RuntimeError(f'Could not activate configured design {settings.DESIGN}')
            session = Session.from_app(expected, app)
            print(f'Verified {actual}; {session.design}; GUI={settings.SHOW_DESKTOP}', flush=True)
            return desktop, session
        except BaseException:
            desktop.release_desktop(close_projects=False, close_on_exit=False)
            raise
