"""Open this file in VS Code and Run Python File, or use the J analysis launch configuration."""
import json

from AnsysSession.GuiRunSettings import prepare

BOARD = 'L4L3_Separate87'
PINS = (317, 376, 399)  # AllCombinationSampler generates all three pairs.


def main():
    options, output = prepare(BOARD, PINS)
    from ansys.aedt.core import settings
    from AnsysSession.ConfiguredSession import open_configured
    from main import run_j_sections

    settings.release_on_exception = False
    settings.enable_global_log_file = settings.enable_local_log_file = False
    desktop, report = None, {'status':'starting', 'board':BOARD, 'pins':list(PINS), 'GUI':True}
    print(f'J analysis results: {output}', flush=True)
    try:
        desktop, session = open_configured(options, output)
        report.update(project=session.path, design=session.design)
        report['results'] = run_j_sections(session, options)
        report['status'] = 'success'
    except Exception as error:
        report.update(status='failed', error=f'{type(error).__name__}: {error}')
        raise
    finally:
        (output/'result.json').write_text(json.dumps(report, indent=2, default=str))
        if desktop:
            desktop.release_desktop(close_projects=False, close_on_exit=False)
        print(f'Run status: {report["status"]}; report: {output/"result.json"}', flush=True)


if __name__ == '__main__':
    main()
