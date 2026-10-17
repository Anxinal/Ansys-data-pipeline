"""Run one analysis setup of an AEDT project and capture its output files.

The project is opened from its file or folder (see opensession.py), the given
setup is solved, and that setup's outputs are exported into one folder:

    <setup>.prof              solve profile (time, memory, mesh size)
    <setup>.conv              adaptive-pass convergence
    <setup>_<sweep>.s<N>p     Touchstone network data (HFSS designs only)
    <report>.csv              data of every report that plots this setup

Usage:
    .venv/bin/python Analysis.py path/to/project.aedt Setup1 [--design NAME] [--output DIR] [--cores N] [--gui]

The default output folder is <project folder>/outputs/<design>/<setup>.
"""

import argparse
import re
from pathlib import Path

from opensession import open_session


def file_stem(name):
    """Make an AEDT name (which may contain spaces or colons) safe for a file name."""
    return re.sub(r"[^\w.-]+", "_", name).strip("_")


def run_analysis(app, setup, cores=None):
    """Solve one setup and save the project so its results are kept."""
    if setup not in app.setup_names:
        raise ValueError(f'No setup "{setup}" in design "{app.design_name}". Available setups: {app.setup_names}')
    print(f'Solving "{setup}" in design "{app.design_name}"...')
    if not app.analyze_setup(setup, cores=cores):
        raise RuntimeError(f'AEDT failed to solve "{setup}". See the AEDT message manager for details.')
    app.save_project()


def capture_outputs(app, setup, output_dir):
    """Export the outputs of a solved setup into output_dir and return the files written."""
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = file_stem(setup)
    outputs = []

    def export(path, exporter):
        path.unlink(missing_ok=True)  # don't mistake a previous run's file for this run's output
        try:
            exporter(str(path))
        except Exception as e:
            print(f"  skipped {path.name}: {e}")
        if path.is_file():
            outputs.append(path)

    export(output_dir / f"{stem}.prof", lambda p: app.export_profile(setup, output_file=p))
    export(output_dir / f"{stem}.conv", lambda p: app.export_convergence(setup, output_file=p))

    if hasattr(app, "export_touchstone"):
        sweeps = [sweep.name for sweep in app.get_setup(setup).sweeps] or ["LastAdaptive"]
        ports = len(app.port_list) if app.design_type == "HFSS 3D Layout Design" else len(app.excitation_names)
        for sweep in sweeps:
            export(
                output_dir / f"{stem}_{file_stem(sweep)}.s{ports}p",
                lambda p: app.export_touchstone(setup, sweep, output_file=p),
            )

    for report in app.post.plots:
        # report.setup is the plotted solution, e.g. "Setup1 : Sweep"
        if report.setup.split(":")[0].strip() == setup:
            app.post.oreportsetup.UpdateReports([report.plot_name])
            export(
                output_dir / f"{file_stem(report.plot_name)}.csv",
                lambda p: app.post.oreportsetup.ExportToFile(report.plot_name, p),
            )

    return outputs


def main():
    parser = argparse.ArgumentParser(description="Solve one AEDT analysis setup and capture its output files.")
    parser.add_argument("path", type=Path, help=".aedt project file, or a folder containing one")
    parser.add_argument("setup", help="analysis setup to solve, e.g. Setup1")
    parser.add_argument("--design", help="design to open (default: the project's active design)")
    parser.add_argument("--output", type=Path, help="folder for the captured files (default: <project folder>/outputs/<design>/<setup>)")
    parser.add_argument("--cores", type=int, help="number of cores for the solve")
    parser.add_argument("--gui", action="store_true", help="show the AEDT GUI")
    args = parser.parse_args()

    app = open_session(args.path, gui=args.gui, design=args.design)
    try:
        run_analysis(app, args.setup, cores=args.cores)
        output_dir = args.output or Path(app.project_path) / "outputs" / file_stem(app.design_name) / file_stem(args.setup)
        outputs = capture_outputs(app, args.setup, output_dir.expanduser().resolve())
    finally:
        app.release_desktop(close_projects=True, close_desktop=True)

    print(f"\nCaptured {len(outputs)} output file(s) in {output_dir}:")
    for path in outputs:
        print(f"  {path.name}")


if __name__ == "__main__":
    main()
