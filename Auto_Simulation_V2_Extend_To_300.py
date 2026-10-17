"""Resume an existing V2 B/J dataset to a total of 300 simulation cases.

RUN: python Auto_Simulation_V2_Extend_To_300.py
The existing local run_config.json is preconfigured below.
Options: --config PATH --project PATH --check-only

Preserve ALL saved coordinates for cases 1-200, including unfinished cases.
Append only cases 201-300, keeping the original seed and geometry settings.
Validate and skip complete B/J pairs; back up partial outputs before re-solving.
Never overwrite the original run_config or the 100/200-case sampling tables.
Persist sampling_300_cases.csv before solving; reload it on subsequent runs.

This script solves pending cases and saves the EXISTING V2 AEDT project.
Close the AEDT window for that V2 project before running; never delete its lock.
The separate FPGA Z-depth AEDT project is not used or modified.
--check-only validates data and the proposed plan without writing dataset files
or starting AEDT. The modeling and field export implementation is retained
from Auto_Simulation_V2_Extend_To_200.py.
"""

from __future__ import annotations

import csv
import json
import math
import time
import traceback
from datetime import datetime
from pathlib import Path

import numpy as np
# Imported only immediately before launching AEDT; --check-only needs NumPy only.


# =============================================================================
# User configuration
# =============================================================================

AEDT_VERSION = "2025.1"
DESIGN_NAME = "Maxwell3DDesign1"
SETUP_NAME = "Setup1"
SOLUTION_NAME = f"{SETUP_NAME} : LastAdaptive"

# 用户设置：留空则运行时弹窗选择旧 run_config.json。
EXISTING_RUN_CONFIG = r"D:\Fan Xinzhe\Auto Simulation Generation\V2\Result\run_20260831_115431_681405\run_config.json"
EXISTING_PROJECT_FILE = r""
TARGET_CASE_COUNT = 300  # 样本总数；seed 从旧 run_config 自动读取，不改成 200。

# Runtime placeholders, replaced from the selected original configuration.
BASE_DIR = Path(".")
RESULT_ROOT = BASE_DIR / "Result"

# Normal new run:
#     RESUME_RUN_ID = None
#
# Resume an interrupted run:
#     1. Open that run's Result\run_...\run_config.json.
#     2. Copy its exact "run_id" value below.
#     3. Close the crashed AEDT session completely, restore the license, and
#        run this same script again.
#
# Resume mode reopens the original AEDT project and original Result folder,
# validates and skips complete B/J pairs, and restarts only the first
# incomplete case.  It never rebuilds the model or starts again at case_0001.
RESUME_RUN_ID: str | None = None

IS_RESUME_RUN = RESUME_RUN_ID is not None
RUN_ID = (
    str(RESUME_RUN_ID)
    if IS_RESUME_RUN
    else datetime.now().strftime("run_%Y%m%d_%H%M%S_%f")
)
PROJECT_FILE = BASE_DIR / f"Deep_Defect_Dataset_V2_{RUN_ID}.aedt"
RUN_RESULT_DIR = RESULT_ROOT / RUN_ID

CURRENT_A = 1.0
CORES = 8

# A slightly tighter solve than V1.  The 30 um values below are field-export
# spacing, not a claim that the tetrahedral FE mesh is exactly 30 um.
CONVERGENCE_PERCENT = 0.5
MAX_ADAPTIVE_PASSES = 30
MIN_ADAPTIVE_PASSES = 2
MIN_CONVERGED_PASSES = 1
INITIAL_MESH_METHOD = "AnsoftClassic"
INITIAL_MESH_LEVEL = 6

ANALYZE = True
CONTINUE_ON_CASE_ERROR = False
SAVE_PROJECT_AFTER_EACH_CASE = True
NON_GRAPHICAL = False
CLOSE_AEDT_WHEN_DONE = False


# =============================================================================
# Geometry dimensions, all in millimetres
# =============================================================================

PCB_SIZE_X_MM = 6.0
PCB_SIZE_Y_MM = 9.0
PCB_THICKNESS_MM = 0.8
PCB_TOP_Z_MM = 0.0

BAR_X_OFFSET_MM = 1.00
BAR_WIDTH_MM = 0.30
BAR_LENGTH_MM = 7.20
BAR_THICKNESS_MM = 0.50
BAR_DEPTH_MM = 0.40

DEFECT_END_OVERLAP_MM = 0.15
DEFECT_LENGTH_MM = (
    2.0 * BAR_X_OFFSET_MM
    - BAR_WIDTH_MM
    + 2.0 * DEFECT_END_OVERLAP_MM
)
DEFECT_WIDTH_MM = 0.12
DEFECT_THICKNESS_MM = 0.06

MIN_COPPER_OVERLAP_MM = 0.05
MIN_DEPTH_CONTAINMENT_MARGIN_MM = 0.005
CLEARANCE_MM = 0.002
LEAD_OVERLAP_MM = 0.050

# Keep the PCB strictly inside the Region.  As in V1, only the two copper feed
# tails extend beyond the PCB and reach the vacuum Region -Y boundary.
TERMINAL_EXTENSION_BEYOND_PCB_MM = 1.0
TERMINAL_Y_MM = -PCB_SIZE_Y_MM / 2.0 - TERMINAL_EXTENSION_BEYOND_PCB_MM
REGION_PADDING_MM = 3.0
REGION_NEGATIVE_Y_PADDING_MM = 0.0


# =============================================================================
# Continuous 100-case sampling
# =============================================================================

N_CASES = TARGET_CASE_COUNT
SAMPLING_SEED = 20260831
LHS_CANDIDATE_COUNT = 64

DEFECT_X_RANGE_MM = (-0.08, 0.08)
DEFECT_Y_RANGE_MM = (-3.20, 3.20)
DEFECT_DEPTH_RANGE_MM = (0.19, 0.61)

NOMINAL_DEFECT_X_MM = 0.0
NOMINAL_DEFECT_Y_MM = 0.0
NOMINAL_DEFECT_DEPTH_MM = 0.40


# =============================================================================
# B and J export grids
# =============================================================================

SCAN_HEIGHT_ABOVE_PCB_MM = 0.060
SCAN_Z_MM = PCB_TOP_Z_MM + SCAN_HEIGHT_ABOVE_PCB_MM

# Full smaller-PCB XY view.  6/0.03=200 and 9/0.03=300 exactly.
B_GRID_START_MM = (-3.0, -4.5, SCAN_Z_MM)
B_GRID_STOP_MM = (3.0, 4.5, SCAN_Z_MM)
B_GRID_STEP_MM = (0.030, 0.030, 0.0)

# J is exported only through the complete conductor depth slab, rather than
# through irrelevant FR4 above and below it.
J_GRID_START_MM = (-3.0, -4.5, -0.65)
J_GRID_STOP_MM = (3.0, 4.5, -0.15)
J_GRID_STEP_MM = (0.030, 0.030, 0.010)

MAX_J_POINTS_PER_CASE = 4_000_000
STORAGE_DTYPE = "float32"
FLD_PARSE_CHUNK_LINES = 100_000

# B FLDs are relatively small and are kept as an auditable raw copy by default.
# J FLD is much larger and is removed only after its NPZ passes validation.
DELETE_B_FLDS_AFTER_VERIFIED_NPZ = False
DELETE_TEMP_J_FLD_AFTER_VERIFIED_NPZ = True

NAMED_B_EXPRESSIONS = {
    "smoothscalBx": "ScalarX",
    "smoothscalBy": "ScalarY",
    "smoothscalBz": "ScalarZ",
}
J_QUANTITY = "J"


# =============================================================================
# AEDT object and boundary names
# =============================================================================

PCB_NAME = "PCB_FR4"
REGION_NAME = "Region"
CONDUCTOR_NAME = "ConductorPath"
RIGHT_BAR_NAME = "RightFixedBar"
DEFECT_NAME = "MovableDefect"
LEFT_LEAD_NAME = "LeftBoundaryLead"
RIGHT_LEAD_NAME = "RightBoundaryLead"

LEFT_BAR_CLEARANCE_NAME = "LeftBarClearance"
RIGHT_BAR_CLEARANCE_NAME = "RightBarClearance"
DEFECT_CLEARANCE_NAME = "DefectClearance"
LEFT_LEAD_CLEARANCE_NAME = "LeftLeadClearance"
RIGHT_LEAD_CLEARANCE_NAME = "RightLeadClearance"

CURRENT_IN_NAME = "DefectCurrentIn"
CURRENT_OUT_NAME = "DefectCurrentOut"


# =============================================================================
# Generic helpers, grids, and sampling
# =============================================================================

def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def mm(value: float) -> str:
    """Format a numeric millimetre value as an AEDT expression."""
    if abs(value) < 5e-13:
        value = 0.0
    return f"{value:.12g}mm"


def axis_count(start: float, stop: float, step: float, axis_name: str) -> int:
    """Return the inclusive point count and reject a truncated grid axis."""
    if math.isclose(start, stop, rel_tol=0.0, abs_tol=1e-12):
        require(step == 0.0, f"{axis_name}: a fixed axis must use zero step.")
        return 1
    require(step > 0.0, f"{axis_name}: step must be positive.")
    intervals = (stop - start) / step
    nearest = round(intervals)
    require(
        math.isclose(intervals, nearest, rel_tol=0.0, abs_tol=1e-9),
        f"{axis_name}: range {stop-start:g} mm is not an integer multiple "
        f"of step {step:g} mm.",
    )
    return int(nearest) + 1


def grid_summary(start_mm, stop_mm, step_mm, label: str) -> dict:
    nx = axis_count(start_mm[0], stop_mm[0], step_mm[0], f"{label} X")
    ny = axis_count(start_mm[1], stop_mm[1], step_mm[1], f"{label} Y")
    nz = axis_count(start_mm[2], stop_mm[2], step_mm[2], f"{label} Z")
    point_count = nx * ny * nz
    return {
        "label": label,
        "start_mm": list(start_mm),
        "stop_mm": list(stop_mm),
        "step_mm": list(step_mm),
        "shape_nx_ny_nz": [nx, ny, nz],
        "point_count": point_count,
    }


def grid_axes(summary: dict):
    nx, ny, nz = summary["shape_nx_ny_nz"]
    start = summary["start_mm"]
    stop = summary["stop_mm"]
    return (
        np.linspace(start[0], stop[0], nx, dtype=np.float64),
        np.linspace(start[1], stop[1], ny, dtype=np.float64),
        np.linspace(start[2], stop[2], nz, dtype=np.float64),
    )


def generate_maximin_lhs_cases() -> tuple[list[dict], float]:
    """Create exactly N_CASES continuous, reproducible 3D sample points."""
    require(N_CASES >= 2, "N_CASES must be at least 2.")
    require(LHS_CANDIDATE_COUNT >= 1, "LHS_CANDIDATE_COUNT must be positive.")
    rng = np.random.default_rng(SAMPLING_SEED)
    best_unit = None
    best_min_distance_sq = -1.0

    for _ in range(LHS_CANDIDATE_COUNT):
        unit = np.empty((N_CASES, 3), dtype=np.float64)
        for dimension in range(3):
            strata = rng.permutation(N_CASES)
            unit[:, dimension] = (
                strata.astype(np.float64) + rng.random(N_CASES)
            ) / N_CASES

        difference = unit[:, None, :] - unit[None, :, :]
        distance_sq = np.einsum("ijk,ijk->ij", difference, difference)
        np.fill_diagonal(distance_sq, np.inf)
        score = float(np.min(distance_sq))
        if score > best_min_distance_sq:
            best_min_distance_sq = score
            best_unit = unit.copy()

    require(best_unit is not None, "Could not generate the Latin hypercube.")
    lower = np.asarray(
        [
            DEFECT_X_RANGE_MM[0],
            DEFECT_Y_RANGE_MM[0],
            DEFECT_DEPTH_RANGE_MM[0],
        ],
        dtype=np.float64,
    )
    upper = np.asarray(
        [
            DEFECT_X_RANGE_MM[1],
            DEFECT_Y_RANGE_MM[1],
            DEFECT_DEPTH_RANGE_MM[1],
        ],
        dtype=np.float64,
    )
    physical = lower + best_unit * (upper - lower)

    cases = []
    for row_index in range(N_CASES):
        cases.append(
            {
                "case_id": f"case_{row_index + 1:04d}",
                "sampling_index": row_index + 1,
                "defect_x_mm": float(physical[row_index, 0]),
                "defect_y_mm": float(physical[row_index, 1]),
                "defect_depth_mm": float(physical[row_index, 2]),
                "lhs_u_x": float(best_unit[row_index, 0]),
                "lhs_u_y": float(best_unit[row_index, 1]),
                "lhs_u_depth": float(best_unit[row_index, 2]),
            }
        )
    return cases, math.sqrt(best_min_distance_sq)


CASES = []
LHS_MIN_NORMALIZED_DISTANCE = 0.0
B_GRID = grid_summary(B_GRID_START_MM, B_GRID_STOP_MM, B_GRID_STEP_MM, "B")
J_GRID = grid_summary(J_GRID_START_MM, J_GRID_STOP_MM, J_GRID_STEP_MM, "J")


def case_geometry_metrics(case: dict) -> dict:
    x_mm = case["defect_x_mm"]
    depth_mm = case["defect_depth_mm"]

    bridge_xmin = x_mm - DEFECT_LENGTH_MM / 2.0
    bridge_xmax = x_mm + DEFECT_LENGTH_MM / 2.0
    left_bar_xmin = -BAR_X_OFFSET_MM - BAR_WIDTH_MM / 2.0
    left_bar_xmax = -BAR_X_OFFSET_MM + BAR_WIDTH_MM / 2.0
    right_bar_xmin = BAR_X_OFFSET_MM - BAR_WIDTH_MM / 2.0
    right_bar_xmax = BAR_X_OFFSET_MM + BAR_WIDTH_MM / 2.0

    left_overlap = (
        min(bridge_xmax, left_bar_xmax)
        - max(bridge_xmin, left_bar_xmin)
    )
    right_overlap = (
        min(bridge_xmax, right_bar_xmax)
        - max(bridge_xmin, right_bar_xmin)
    )

    bar_depth_min = BAR_DEPTH_MM - BAR_THICKNESS_MM / 2.0
    bar_depth_max = BAR_DEPTH_MM + BAR_THICKNESS_MM / 2.0
    bridge_depth_min = depth_mm - DEFECT_THICKNESS_MM / 2.0
    bridge_depth_max = depth_mm + DEFECT_THICKNESS_MM / 2.0
    return {
        "left_x_overlap_mm": left_overlap,
        "right_x_overlap_mm": right_overlap,
        "bar_depth_interval_mm": [bar_depth_min, bar_depth_max],
        "bridge_depth_interval_mm": [bridge_depth_min, bridge_depth_max],
        "top_depth_margin_mm": bridge_depth_min - bar_depth_min,
        "bottom_depth_margin_mm": bar_depth_max - bridge_depth_max,
    }


def check_configuration() -> None:
    """Validate all 100 cases and grids before AEDT starts."""
    require(len(CASES) == N_CASES, f"Expected {N_CASES} cases, received {len(CASES)}.")
    require(len({case["case_id"] for case in CASES}) == N_CASES,
            "Case IDs are not unique.")
    require(CURRENT_A > 0.0, "CURRENT_A must be positive.")
    require(CORES >= 1, "CORES must be at least 1.")
    require(CLEARANCE_MM > 0.0, "CLEARANCE_MM must be positive.")
    require(DEFECT_LENGTH_MM > 0.0 and DEFECT_WIDTH_MM > 0.0
            and DEFECT_THICKNESS_MM > 0.0,
            "All defect dimensions must be positive.")
    require(BAR_WIDTH_MM > 0.0 and BAR_THICKNESS_MM > 0.0,
            "Bar width and thickness must be positive.")
    require(BAR_LENGTH_MM < PCB_SIZE_Y_MM,
            "The fixed bars must fit inside the PCB in Y.")
    require(
        TERMINAL_Y_MM < -PCB_SIZE_Y_MM / 2.0,
        "TERMINAL_Y_MM must lie beyond the PCB -Y edge, as in V1.",
    )
    require(
        TERMINAL_Y_MM < -BAR_LENGTH_MM / 2.0,
        "TERMINAL_Y_MM must lie beyond the fixed-rail -Y ends.",
    )
    require(
        math.isclose(
            -PCB_SIZE_Y_MM / 2.0 - TERMINAL_Y_MM,
            TERMINAL_EXTENSION_BEYOND_PCB_MM,
            rel_tol=0.0,
            abs_tol=1e-12,
        ),
        "Terminal extension and terminal plane are inconsistent.",
    )
    require(REGION_NEGATIVE_Y_PADDING_MM == 0.0,
            "Region -Y padding must be zero at the terminal wall.")
    require(REGION_PADDING_MM > 0.0,
            "Non-terminal Region padding must be positive.")
    require(
        BAR_X_OFFSET_MM + BAR_WIDTH_MM / 2.0
        < PCB_SIZE_X_MM / 2.0,
        "The fixed bars do not fit inside the PCB in X.",
    )
    require(
        BAR_DEPTH_MM - BAR_THICKNESS_MM / 2.0 - CLEARANCE_MM > 0.0
        and BAR_DEPTH_MM + BAR_THICKNESS_MM / 2.0 + CLEARANCE_MM
        < PCB_THICKNESS_MM,
        "The fixed rails or their clearance break a PCB Z surface.",
    )
    require(INITIAL_MESH_METHOD in {"AnsoftClassic", "AnsoftTAU", "Auto"},
            "Unsupported initial mesh method.")
    require(1 <= INITIAL_MESH_LEVEL <= 10,
            "INITIAL_MESH_LEVEL must be between 1 and 10.")

    for case in CASES:
        x_mm = case["defect_x_mm"]
        y_mm = case["defect_y_mm"]
        depth_mm = case["defect_depth_mm"]
        require(DEFECT_X_RANGE_MM[0] <= x_mm <= DEFECT_X_RANGE_MM[1],
                f"{case['case_id']} X lies outside its sampling range.")
        require(DEFECT_Y_RANGE_MM[0] <= y_mm <= DEFECT_Y_RANGE_MM[1],
                f"{case['case_id']} Y lies outside its sampling range.")
        require(
            DEFECT_DEPTH_RANGE_MM[0]
            <= depth_mm
            <= DEFECT_DEPTH_RANGE_MM[1],
            f"{case['case_id']} depth lies outside its sampling range.",
        )

        metrics = case_geometry_metrics(case)
        require(
            metrics["left_x_overlap_mm"] >= MIN_COPPER_OVERLAP_MM,
            f"{case['case_id']} has insufficient left-rail overlap.",
        )
        require(
            metrics["right_x_overlap_mm"] >= MIN_COPPER_OVERLAP_MM,
            f"{case['case_id']} has insufficient right-rail overlap.",
        )

        bridge_ymin = y_mm - DEFECT_WIDTH_MM / 2.0
        bridge_ymax = y_mm + DEFECT_WIDTH_MM / 2.0
        require(
            bridge_ymin > -BAR_LENGTH_MM / 2.0
            and bridge_ymax < BAR_LENGTH_MM / 2.0,
            f"{case['case_id']} places the bridge beyond a rail end.",
        )
        require(
            metrics["top_depth_margin_mm"]
            >= MIN_DEPTH_CONTAINMENT_MARGIN_MM
            and metrics["bottom_depth_margin_mm"]
            >= MIN_DEPTH_CONTAINMENT_MARGIN_MM,
            f"{case['case_id']} bridge is not fully contained in rail depth.",
        )
        require(
            depth_mm - DEFECT_THICKNESS_MM / 2.0 - CLEARANCE_MM > 0.0
            and depth_mm + DEFECT_THICKNESS_MM / 2.0 + CLEARANCE_MM
            < PCB_THICKNESS_MM,
            f"{case['case_id']} defect clearance breaks a PCB Z surface.",
        )

    require(B_GRID["shape_nx_ny_nz"] == [201, 301, 1],
            f"Unexpected B grid shape: {B_GRID['shape_nx_ny_nz']}")
    require(J_GRID["shape_nx_ny_nz"] == [201, 301, 51],
            f"Unexpected J grid shape: {J_GRID['shape_nx_ny_nz']}")
    require(
        J_GRID["point_count"] <= MAX_J_POINTS_PER_CASE,
        f"J grid has {J_GRID['point_count']:,} points, exceeding "
        f"MAX_J_POINTS_PER_CASE={MAX_J_POINTS_PER_CASE:,}.",
    )
    require(B_GRID_START_MM[0] <= -PCB_SIZE_X_MM / 2.0
            and B_GRID_STOP_MM[0] >= PCB_SIZE_X_MM / 2.0
            and B_GRID_START_MM[1] <= -PCB_SIZE_Y_MM / 2.0
            and B_GRID_STOP_MM[1] >= PCB_SIZE_Y_MM / 2.0,
            "The B grid no longer covers the complete small PCB in XY.")
    require(
        J_GRID_START_MM[2]
        <= -BAR_DEPTH_MM - BAR_THICKNESS_MM / 2.0
        and J_GRID_STOP_MM[2]
        >= -BAR_DEPTH_MM + BAR_THICKNESS_MM / 2.0,
        "The J Z grid does not cover the complete fixed rails.",
    )

    BASE_DIR.mkdir(parents=True, exist_ok=True)
    RESULT_ROOT.mkdir(parents=True, exist_ok=True)
    if IS_RESUME_RUN:
        require(
            RUN_RESULT_DIR.is_dir(),
            f"Resume Result folder does not exist: {RUN_RESULT_DIR}",
        )
        require(
            PROJECT_FILE.is_file(),
            f"Resume AEDT project does not exist: {PROJECT_FILE}",
        )
    else:
        RUN_RESULT_DIR.mkdir(parents=True, exist_ok=False)


def validate_existing_run_inputs() -> None:
    """Prove that the selected old run uses these exact 100 sample points."""
    require(IS_RESUME_RUN, "Existing-run validation requires resume mode.")
    config_path = RUN_RESULT_DIR / "run_config.json"
    sampling_path = RUN_RESULT_DIR / "sampling_100_cases.csv"
    require(config_path.is_file(), f"Missing resume config: {config_path}")
    require(sampling_path.is_file(), f"Missing resume sample table: {sampling_path}")

    with config_path.open("r", encoding="utf-8") as stream:
        old_config = json.load(stream)
    require(
        old_config.get("run_id") == RUN_ID,
        f"run_config.json belongs to {old_config.get('run_id')!r}, "
        f"not {RUN_ID!r}.",
    )

    with sampling_path.open("r", newline="", encoding="utf-8-sig") as stream:
        old_rows = list(csv.DictReader(stream))
    require(
        len(old_rows) == len(CASES),
        f"Resume sample table has {len(old_rows)} rows; expected {len(CASES)}.",
    )
    for expected, old in zip(CASES, old_rows):
        require(
            old.get("case_id") == expected["case_id"],
            f"Resume sample order differs at {expected['case_id']}.",
        )
        for column in ("defect_x_mm", "defect_y_mm", "defect_depth_mm"):
            try:
                old_value = float(old[column])
            except (KeyError, TypeError, ValueError) as exc:
                raise RuntimeError(
                    f"Invalid {column} in resume sample {expected['case_id']}."
                ) from exc
            require(
                math.isclose(
                    old_value,
                    expected[column],
                    rel_tol=0.0,
                    abs_tol=1e-12,
                ),
                f"Resume sample {expected['case_id']} has changed {column}: "
                f"old={old_value}, current={expected[column]}.",
            )


def write_sampling_table() -> None:
    columns = [
        "case_id",
        "sampling_index",
        "defect_x_mm",
        "defect_y_mm",
        "defect_depth_mm",
        "lhs_u_x",
        "lhs_u_y",
        "lhs_u_depth",
    ]
    output_path = RUN_RESULT_DIR / "sampling_100_cases.csv"
    with output_path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for case in CASES:
            writer.writerow({name: case[name] for name in columns})


def configuration_dictionary() -> dict:
    nx_j, ny_j, nz_j = J_GRID["shape_nx_ny_nz"]
    j_dense_mib = 3 * nx_j * ny_j * nz_j * np.dtype(STORAGE_DTYPE).itemsize / 1024**2
    config = {
        "run_id": RUN_ID,
        "project_file": str(PROJECT_FILE),
        "result_directory": str(RUN_RESULT_DIR),
        "software": {
            "aedt": AEDT_VERSION,
            "expected_pyaedt": "1.3.0",
            "solver": "Maxwell 3D Magnetostatic",
        },
        "geometry_mm": {
            "pcb": [PCB_SIZE_X_MM, PCB_SIZE_Y_MM, PCB_THICKNESS_MM],
            "pcb_top_z": PCB_TOP_Z_MM,
            "fixed_rail_x_centres": [-BAR_X_OFFSET_MM, BAR_X_OFFSET_MM],
            "fixed_rail_width": BAR_WIDTH_MM,
            "fixed_rail_length": BAR_LENGTH_MM,
            "fixed_rail_thickness": BAR_THICKNESS_MM,
            "fixed_rail_centre_depth": BAR_DEPTH_MM,
            "fixed_rail_depth_interval": [
                BAR_DEPTH_MM - BAR_THICKNESS_MM / 2.0,
                BAR_DEPTH_MM + BAR_THICKNESS_MM / 2.0,
            ],
            "defect_shape": "straight rectangular copper bridge",
            "defect_dimensions": [
                DEFECT_LENGTH_MM,
                DEFECT_WIDTH_MM,
                DEFECT_THICKNESS_MM,
            ],
            "nominal_end_overlap": DEFECT_END_OVERLAP_MM,
            "minimum_allowed_overlap": MIN_COPPER_OVERLAP_MM,
            "fr4_clearance": CLEARANCE_MM,
            "terminal_y": TERMINAL_Y_MM,
            "terminal_extension_beyond_pcb":
                TERMINAL_EXTENSION_BEYOND_PCB_MM,
            "region_padding": REGION_PADDING_MM,
            "region_negative_y_padding": REGION_NEGATIVE_Y_PADDING_MM,
        },
        "sampling": {
            "method": "maximin Latin hypercube",
            "case_count": N_CASES,
            "seed": SAMPLING_SEED,
            "candidate_count": LHS_CANDIDATE_COUNT,
            "selected_min_normalized_distance": LHS_MIN_NORMALIZED_DISTANCE,
            "ranges_mm": {
                "defect_x": list(DEFECT_X_RANGE_MM),
                "defect_y": list(DEFECT_Y_RANGE_MM),
                "defect_depth": list(DEFECT_DEPTH_RANGE_MM),
            },
            "table": "sampling_100_cases.csv",
        },
        "B_export": {
            "quantity": "Smooth scalar components of B",
            "components": ["Bx", "By", "Bz"],
            "grid": B_GRID,
            "tensor_layout": "[component,y,x]",
            "storage_dtype": STORAGE_DTYPE,
            "npz_name": "B_2D_float32.npz",
            "raw_fld_kept": not DELETE_B_FLDS_AFTER_VERIFIED_NPZ,
        },
        "J_export": {
            "quantity": "raw vector current density J",
            "components": ["Jx", "Jy", "Jz"],
            "grid": J_GRID,
            "domain_note": (
                "Complete small-PCB XY area and complete conductor depth slab; "
                "the external terminal tails beyond PCB -Y are intentionally "
                "excluded from the training label."
            ),
            "tensor_layout": "[component,z,y,x]",
            "storage_dtype": STORAGE_DTYPE,
            "nonfinite_policy": (
                "Match the proven V1 add-on: replace NaN/Inf with zero during "
                "FLD conversion and record the exact replacement count."
            ),
            "dense_tensor_MiB_per_case": j_dense_mib,
            "npz_name": "J_3D_float32.npz",
            "temporary_fld_deleted_after_validation":
                DELETE_TEMP_J_FLD_AFTER_VERIFIED_NPZ,
        },
        "excitation": {
            "current_A": CURRENT_A,
            "current_in": CURRENT_IN_NAME,
            "current_out": CURRENT_OUT_NAME,
        },
        "mesh_and_solver": {
            "initial_mesh_method": INITIAL_MESH_METHOD,
            "initial_mesh_level": INITIAL_MESH_LEVEL,
            "phi": False,
            "fallback": False,
            "adaptive_percent_error": CONVERGENCE_PERCENT,
            "minimum_passes": MIN_ADAPTIVE_PASSES,
            "maximum_passes": MAX_ADAPTIVE_PASSES,
            "minimum_converged_passes": MIN_CONVERGED_PASSES,
        },
        "normalization_warning": (
            "Do not independently max-normalize each B sample; absolute B "
            "amplitude contains defect-depth information."
        ),
    }
    return config


def write_run_configuration() -> None:
    raise RuntimeError("Extension mode never overwrites the original run_config.json.")


# =============================================================================
# Parametric Maxwell model
# =============================================================================

def set_variable(app: Maxwell3d, name: str, expression: str, sweep: bool) -> None:
    ok = app.variable_manager.set_variable(
        name=name,
        expression=expression,
        sweep=sweep,
        overwrite=True,
    )
    require(ok is not False, f"Could not set design variable {name}={expression}.")


def add_design_variables(app: Maxwell3d) -> None:
    set_variable(app, "pcb_size_x", mm(PCB_SIZE_X_MM), False)
    set_variable(app, "pcb_size_y", mm(PCB_SIZE_Y_MM), False)
    set_variable(app, "pcb_thickness", mm(PCB_THICKNESS_MM), False)
    set_variable(app, "pcb_top_z", mm(PCB_TOP_Z_MM), False)
    set_variable(app, "bar_x_offset", mm(BAR_X_OFFSET_MM), False)
    set_variable(app, "bar_width", mm(BAR_WIDTH_MM), False)
    set_variable(app, "bar_length", mm(BAR_LENGTH_MM), False)
    set_variable(app, "bar_thickness", mm(BAR_THICKNESS_MM), False)
    set_variable(app, "bar_depth", mm(BAR_DEPTH_MM), False)
    set_variable(app, "bar_center_z", "pcb_top_z-bar_depth", False)
    set_variable(app, "defect_length", mm(DEFECT_LENGTH_MM), False)
    set_variable(app, "defect_width", mm(DEFECT_WIDTH_MM), False)
    set_variable(app, "defect_thickness", mm(DEFECT_THICKNESS_MM), False)
    set_variable(app, "clearance", mm(CLEARANCE_MM), False)

    set_variable(app, "defect_x", mm(NOMINAL_DEFECT_X_MM), True)
    set_variable(app, "defect_y", mm(NOMINAL_DEFECT_Y_MM), True)
    set_variable(app, "defect_depth", mm(NOMINAL_DEFECT_DEPTH_MM), True)

    set_variable(app, "left_bar_x", "-bar_x_offset", False)
    set_variable(app, "right_bar_x", "bar_x_offset", False)
    set_variable(app, "defect_z", "pcb_top_z-defect_depth", False)


def set_model_state_explicit(app: Maxwell3d, names, model: bool) -> None:
    object_names = [str(name) for name in names]
    if not object_names:
        return
    app.modeler.oeditor.ChangeProperty(
        [
            "NAME:AllTabs",
            [
                "NAME:Geometry3DAttributeTab",
                ["NAME:PropServers", *object_names],
                ["NAME:ChangedProps", ["NAME:Model", "Value:=", bool(model)]],
            ],
        ]
    )


def create_box(app: Maxwell3d, origin, sizes, name: str, material: str):
    body = app.modeler.create_box(
        origin=origin,
        sizes=sizes,
        name=name,
        material=material,
    )
    require(body, f"CreateBox failed for {name}.")
    return body


def create_straight_bridge_box(
    app: Maxwell3d,
    name: str,
    material: str,
    add_clearance: bool,
):
    if add_clearance:
        origin = [
            "defect_x-defect_length/2-clearance",
            "defect_y-defect_width/2-clearance",
            "defect_z-defect_thickness/2-clearance",
        ]
        sizes = [
            "defect_length+2*clearance",
            "defect_width+2*clearance",
            "defect_thickness+2*clearance",
        ]
    else:
        origin = [
            "defect_x-defect_length/2",
            "defect_y-defect_width/2",
            "defect_z-defect_thickness/2",
        ]
        sizes = ["defect_length", "defect_width", "defect_thickness"]
    return create_box(app, origin, sizes, name, material)


def create_interior_geometry(app: Maxwell3d) -> None:
    pcb = create_box(
        app,
        ["-pcb_size_x/2", "-pcb_size_y/2", "pcb_top_z-pcb_thickness"],
        ["pcb_size_x", "pcb_size_y", "pcb_thickness"],
        PCB_NAME,
        "FR4_epoxy",
    )
    pcb.solve_inside = True

    left_bar = create_box(
        app,
        [
            "left_bar_x-bar_width/2",
            "-bar_length/2",
            "bar_center_z-bar_thickness/2",
        ],
        ["bar_width", "bar_length", "bar_thickness"],
        CONDUCTOR_NAME,
        "copper",
    )
    right_bar = create_box(
        app,
        [
            "right_bar_x-bar_width/2",
            "-bar_length/2",
            "bar_center_z-bar_thickness/2",
        ],
        ["bar_width", "bar_length", "bar_thickness"],
        RIGHT_BAR_NAME,
        "copper",
    )
    defect = create_straight_bridge_box(
        app, DEFECT_NAME, "copper", add_clearance=False
    )
    left_bar.solve_inside = True
    right_bar.solve_inside = True
    defect.solve_inside = True

    create_box(
        app,
        [
            "left_bar_x-bar_width/2-clearance",
            "-bar_length/2-clearance",
            "bar_center_z-bar_thickness/2-clearance",
        ],
        [
            "bar_width+2*clearance",
            "bar_length+2*clearance",
            "bar_thickness+2*clearance",
        ],
        LEFT_BAR_CLEARANCE_NAME,
        "vacuum",
    )
    create_box(
        app,
        [
            "right_bar_x-bar_width/2-clearance",
            "-bar_length/2-clearance",
            "bar_center_z-bar_thickness/2-clearance",
        ],
        [
            "bar_width+2*clearance",
            "bar_length+2*clearance",
            "bar_thickness+2*clearance",
        ],
        RIGHT_BAR_CLEARANCE_NAME,
        "vacuum",
    )
    create_straight_bridge_box(
        app, DEFECT_CLEARANCE_NAME, "vacuum", add_clearance=True
    )


def create_boundary_leads_and_cutters(app: Maxwell3d):
    bar_ymin = -BAR_LENGTH_MM / 2.0
    lead_length = bar_ymin + LEAD_OVERLAP_MM - TERMINAL_Y_MM
    require(lead_length > 0.0, "Terminal plane leaves no room for feed leads.")

    for name, x_expression in (
        (LEFT_LEAD_NAME, "left_bar_x"),
        (RIGHT_LEAD_NAME, "right_bar_x"),
    ):
        lead = create_box(
            app,
            [
                f"{x_expression}-bar_width/2",
                mm(TERMINAL_Y_MM),
                "bar_center_z-bar_thickness/2",
            ],
            ["bar_width", mm(lead_length), "bar_thickness"],
            name,
            "copper",
        )
        lead.solve_inside = True

    for name, x_expression in (
        (LEFT_LEAD_CLEARANCE_NAME, "left_bar_x"),
        (RIGHT_LEAD_CLEARANCE_NAME, "right_bar_x"),
    ):
        create_box(
            app,
            [
                f"{x_expression}-bar_width/2-clearance",
                mm(TERMINAL_Y_MM),
                "bar_center_z-bar_thickness/2-clearance",
            ],
            [
                "bar_width+2*clearance",
                mm(lead_length),
                "bar_thickness+2*clearance",
            ],
            name,
            "vacuum",
        )

    return (
        [-BAR_X_OFFSET_MM, TERMINAL_Y_MM, -BAR_DEPTH_MM],
        [BAR_X_OFFSET_MM, TERMINAL_Y_MM, -BAR_DEPTH_MM],
    )


def cut_pcb_clearances(app: Maxwell3d) -> None:
    cutters = [
        LEFT_BAR_CLEARANCE_NAME,
        RIGHT_BAR_CLEARANCE_NAME,
        DEFECT_CLEARANCE_NAME,
        LEFT_LEAD_CLEARANCE_NAME,
        RIGHT_LEAD_CLEARANCE_NAME,
    ]
    result = app.modeler.subtract(
        blank_list=[PCB_NAME],
        tool_list=cutters,
        keep_originals=False,
    )
    app.modeler.refresh_all_ids()
    require(result is not False, "Subtracting copper clearances from PCB failed.")
    require(PCB_NAME in app.modeler.object_names,
            "PCB disappeared after the clearance subtraction.")
    remaining = [name for name in cutters if name in app.modeler.object_names]
    require(not remaining, f"Clearance cutters remained: {remaining}")


def unite_conductor_path(app: Maxwell3d) -> None:
    conductor_parts = [
        CONDUCTOR_NAME,
        RIGHT_BAR_NAME,
        DEFECT_NAME,
        LEFT_LEAD_NAME,
        RIGHT_LEAD_NAME,
    ]
    result = app.modeler.unite(
        assignment=conductor_parts,
        purge=False,
        keep_originals=False,
    )
    app.modeler.refresh_all_ids()
    require(result, f"Unite failed for {conductor_parts}.")
    require(CONDUCTOR_NAME in app.modeler.object_names,
            "United conductor lost its expected name.")
    remaining = [
        name for name in conductor_parts[1:]
        if name in app.modeler.object_names
    ]
    require(not remaining, f"Unite left separate copper objects: {remaining}")
    conductor = app.modeler.get_object_from_name(CONDUCTOR_NAME)
    require(conductor is not None, "Could not retrieve the united conductor.")
    conductor.material_name = "copper"
    conductor.solve_inside = True
    set_model_state_explicit(app, [CONDUCTOR_NAME, PCB_NAME], True)


def create_native_vacuum_region(app: Maxwell3d):
    padding = [
        mm(REGION_PADDING_MM),
        mm(REGION_PADDING_MM),
        mm(REGION_PADDING_MM),
        mm(REGION_NEGATIVE_Y_PADDING_MM),
        mm(REGION_PADDING_MM),
        mm(REGION_PADDING_MM),
    ]
    region = app.modeler.create_region(
        pad_value=padding,
        pad_type="Absolute Offset",
        name=REGION_NAME,
    )
    require(region, "AEDT CreateRegion failed.")
    try:
        region.material_name = "vacuum"
    except Exception:
        pass
    set_model_state_explicit(app, [REGION_NAME], True)
    return region


def numeric_bounds(obj, label: str):
    raw = list(obj.bounding_box)
    require(len(raw) == 6, f"Unexpected {label} bounding box: {raw}")
    try:
        bounds = [float(value) for value in raw]
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"{label} bounding box is not numeric: {raw}") from exc
    xmin, ymin, zmin, xmax, ymax, zmax = bounds
    require(xmin < xmax and ymin < ymax and zmin < zmax,
            f"Invalid {label} bounds: {bounds}")
    return bounds


def verify_copper_is_clear_of_fr4(app: Maxwell3d, region_bounds) -> None:
    pcb_ymin = -PCB_SIZE_Y_MM / 2.0
    external_lead_probe_y = (TERMINAL_Y_MM + pcb_ymin) / 2.0
    internal_lead_probe_y = pcb_ymin + 0.5
    rail_probe_y = BAR_LENGTH_MM / 2.0 - 0.5
    probes = [
        ([-BAR_X_OFFSET_MM, rail_probe_y, -BAR_DEPTH_MM], "left rail"),
        ([BAR_X_OFFSET_MM, rail_probe_y, -BAR_DEPTH_MM], "right rail"),
        ([NOMINAL_DEFECT_X_MM, NOMINAL_DEFECT_Y_MM,
          -NOMINAL_DEFECT_DEPTH_MM], "nominal bridge"),
        ([-BAR_X_OFFSET_MM, external_lead_probe_y, -BAR_DEPTH_MM],
         "left external feed"),
        ([BAR_X_OFFSET_MM, external_lead_probe_y, -BAR_DEPTH_MM],
         "right external feed"),
        ([-BAR_X_OFFSET_MM, internal_lead_probe_y, -BAR_DEPTH_MM],
         "left in-PCB feed"),
        ([BAR_X_OFFSET_MM, internal_lead_probe_y, -BAR_DEPTH_MM],
         "right in-PCB feed"),
    ]
    require(region_bounds[1] < external_lead_probe_y < pcb_ymin,
            "The external feed probe is not between PCB and Region walls.")
    require(pcb_ymin < internal_lead_probe_y < -BAR_LENGTH_MM / 2.0,
            "The in-PCB feed probe is not inside the feed segment.")
    for point, label in probes:
        bodies = set(app.modeler.get_bodynames_from_position(point, units="mm"))
        require(CONDUCTOR_NAME in bodies,
                f"Conductor missing at {label} probe {point}; bodies={sorted(bodies)}")
        require(PCB_NAME not in bodies,
                f"Copper overlaps FR4 at {label} probe {point}; "
                f"bodies={sorted(bodies)}")


def find_terminal_face(app: Maxwell3d, point, label: str) -> int:
    face_id = app.modeler.get_faceid_from_position(
        point,
        assignment=CONDUCTOR_NAME,
        units="mm",
    )
    require(isinstance(face_id, int) and face_id >= 0,
            f"Could not find the {label} terminal face at {point}.")
    expected_area = BAR_WIDTH_MM * BAR_THICKNESS_MM
    area = float(app.modeler.get_face_area(face_id))
    relative_error = abs(area - expected_area) / expected_area
    require(relative_error <= 0.10,
            f"{label} terminal area={area:.9g} mm^2; "
            f"expected {expected_area:.9g} mm^2.")
    return int(face_id)


def verify_and_resolve_terminals(
    app: Maxwell3d,
    left_terminal,
    right_terminal,
    region_bounds,
):
    region_ymin = region_bounds[1]
    for label, point in (("left", left_terminal), ("right", right_terminal)):
        require(abs(point[1] - region_ymin) <= 1e-7,
                f"{label} terminal is not exactly on Region ymin.")

    conductor = app.modeler.get_object_from_name(CONDUCTOR_NAME)
    conductor_bounds = numeric_bounds(conductor, CONDUCTOR_NAME)
    require(abs(conductor_bounds[1] - region_ymin) <= 1e-6,
            "Conductor ymin and Region ymin do not coincide.")
    require(
        conductor_bounds[0] > region_bounds[0]
        and conductor_bounds[3] < region_bounds[3]
        and conductor_bounds[2] > region_bounds[2]
        and conductor_bounds[5] < region_bounds[5],
        "Copper exceeds a non-terminal Region wall.",
    )

    pcb = app.modeler.get_object_from_name(PCB_NAME)
    require(pcb is not None, f"Could not retrieve {PCB_NAME}.")
    pcb_bounds = numeric_bounds(pcb, PCB_NAME)
    require(
        pcb_bounds[0] > region_bounds[0]
        and pcb_bounds[1] > region_bounds[1]
        and pcb_bounds[2] > region_bounds[2]
        and pcb_bounds[3] < region_bounds[3]
        and pcb_bounds[4] < region_bounds[4]
        and pcb_bounds[5] < region_bounds[5],
        "The PCB must remain strictly inside the Region; only the two copper "
        "terminal faces may touch the Region boundary.",
    )

    left_face = find_terminal_face(app, left_terminal, "left")
    right_face = find_terminal_face(app, right_terminal, "right")
    require(left_face != right_face, "Both terminals resolved to one face.")
    return left_face, right_face


def assign_direct_currents(app: Maxwell3d, left_face: int, right_face: int) -> None:
    current_expression = f"{CURRENT_A:.12g}A"
    current_in = app.assign_current(
        assignment=[left_face],
        amplitude=current_expression,
        solid=True,
        swap_direction=False,
        name=CURRENT_IN_NAME,
    )
    current_out = app.assign_current(
        assignment=[right_face],
        amplitude=current_expression,
        solid=True,
        swap_direction=True,
        name=CURRENT_OUT_NAME,
    )
    require(current_in and current_out,
            "Failed to create both direct Current boundaries.")
    expected = {CURRENT_IN_NAME, CURRENT_OUT_NAME}
    actual = {boundary.name for boundary in app.boundaries}
    require(expected.issubset(actual),
            f"Incomplete Current registration: {actual}")


def configure_initial_mesh_explicitly(app: Maxwell3d) -> None:
    """Use the proven raw Maxwell MeshSetup API from V1."""
    mesh_settings = [
        "NAME:MeshSettings",
        [
            "NAME:GlobalSurfApproximation",
            "CurvedSurfaceApproxChoice:=",
            "UseSlider",
            "SliderMeshSettings:=",
            int(INITIAL_MESH_LEVEL),
        ],
        ["NAME:GlobalCurvilinear", "Apply:=", False],
        ["NAME:GlobalModelRes", "UseAutoLength:=", True],
        "MeshMethod:=",
        INITIAL_MESH_METHOD,
        "UseLegacyFaceterForTauVolumeMesh:=",
        False,
        "DynamicSurfaceResolution:=",
        False,
        "UseFlexMeshingForTAUvolumeMesh:=",
        False,
        "UseAlternativeMeshMethodsAsFallBack:=",
        False,
        "AllowPhiForLayeredGeometry:=",
        False,
    ]
    app.mesh.omeshmodule.InitialMeshSettings(mesh_settings)


def configure_solver(app: Maxwell3d) -> None:
    if SETUP_NAME in app.setup_names:
        deleted = app.delete_setup(SETUP_NAME)
        require(deleted is not False, f"Could not delete old {SETUP_NAME}.")
    setup = app.create_setup(
        name=SETUP_NAME,
        setup_type="Magnetostatic",
        MaximumPasses=int(MAX_ADAPTIVE_PASSES),
        MinimumPasses=int(MIN_ADAPTIVE_PASSES),
        MinimumConvergedPasses=int(MIN_CONVERGED_PASSES),
        PercentError=float(CONVERGENCE_PERCENT),
    )
    require(setup, f"Could not create {SETUP_NAME}.")
    require(setup.update() is not False, f"Could not update {SETUP_NAME}.")
    configure_initial_mesh_explicitly(app)


def create_b_component_named_expressions(app: Maxwell3d) -> None:
    calculator = app.ofieldsreporter
    for expression_name, scalar_operation in NAMED_B_EXPRESSIONS.items():
        calculator.CalcStack("clear")
        calculator.EnterQty("B")
        calculator.CalcOp(scalar_operation)
        calculator.CalcOp("Smooth")
        calculator.AddNamedExpression(expression_name, "Fields")
        calculator.CalcStack("clear")


def build_model(app: Maxwell3d) -> None:
    app.modeler.model_units = "mm"
    add_design_variables(app)
    create_interior_geometry(app)
    left_terminal, right_terminal = create_boundary_leads_and_cutters(app)
    cut_pcb_clearances(app)
    unite_conductor_path(app)

    region = create_native_vacuum_region(app)
    region_bounds = numeric_bounds(region, REGION_NAME)
    print(
        "Region bounds (mm): "
        f"x=[{region_bounds[0]}, {region_bounds[3]}], "
        f"y=[{region_bounds[1]}, {region_bounds[4]}], "
        f"z=[{region_bounds[2]}, {region_bounds[5]}]"
    )
    verify_copper_is_clear_of_fr4(app, region_bounds)
    left_face, right_face = verify_and_resolve_terminals(
        app, left_terminal, right_terminal, region_bounds
    )
    assign_direct_currents(app, left_face, right_face)
    configure_solver(app)
    create_b_component_named_expressions(app)

    pcb = app.modeler.get_object_from_name(PCB_NAME)
    conductor = app.modeler.get_object_from_name(CONDUCTOR_NAME)
    require(pcb is not None and conductor is not None,
            "Required model objects are missing.")
    require(str(pcb.material_name).strip().lower() == "fr4_epoxy",
            f"PCB material is {pcb.material_name!r}.")
    require(str(conductor.material_name).strip().lower() == "copper",
            f"Conductor material is {conductor.material_name!r}.")
    require(str(region.material_name).strip().lower() == "vacuum",
            f"Region material is {region.material_name!r}.")


# =============================================================================
# Case state and AEDT field export
# =============================================================================

def set_case_variables(app: Maxwell3d, case: dict) -> None:
    set_variable(app, "defect_x", mm(case["defect_x_mm"]), True)
    set_variable(app, "defect_y", mm(case["defect_y_mm"]), True)
    set_variable(app, "defect_depth", mm(case["defect_depth_mm"]), True)


def verify_case_straight_bridge(app: Maxwell3d, case: dict) -> dict:
    x_mm = case["defect_x_mm"]
    y_mm = case["defect_y_mm"]
    depth_mm = case["defect_depth_mm"]
    metrics = case_geometry_metrics(case)

    bridge_xmin = x_mm - DEFECT_LENGTH_MM / 2.0
    bridge_xmax = x_mm + DEFECT_LENGTH_MM / 2.0
    left_bar_xmin = -BAR_X_OFFSET_MM - BAR_WIDTH_MM / 2.0
    left_bar_xmax = -BAR_X_OFFSET_MM + BAR_WIDTH_MM / 2.0
    right_bar_xmin = BAR_X_OFFSET_MM - BAR_WIDTH_MM / 2.0
    right_bar_xmax = BAR_X_OFFSET_MM + BAR_WIDTH_MM / 2.0

    left_overlap_min = max(bridge_xmin, left_bar_xmin)
    left_overlap_max = min(bridge_xmax, left_bar_xmax)
    right_overlap_min = max(bridge_xmin, right_bar_xmin)
    right_overlap_max = min(bridge_xmax, right_bar_xmax)
    probe_z = -depth_mm

    probes = [
        ([x_mm, y_mm, probe_z], "bridge centre"),
        ([(left_overlap_min + left_overlap_max) / 2.0, y_mm, probe_z],
         "left bridge/rail overlap"),
        ([(right_overlap_min + right_overlap_max) / 2.0, y_mm, probe_z],
         "right bridge/rail overlap"),
    ]
    app.modeler.refresh_all_ids()
    for point, label in probes:
        bodies = set(app.modeler.get_bodynames_from_position(point, units="mm"))
        require(CONDUCTOR_NAME in bodies,
                f"Missing copper at {label} {point}; bodies={sorted(bodies)}")
        require(PCB_NAME not in bodies,
                f"Copper overlaps FR4 at {label} {point}; "
                f"bodies={sorted(bodies)}")
    return metrics


def variation_list(case: dict) -> list:
    return [
        "defect_x:=", [mm(case["defect_x_mm"])],
        "defect_y:=", [mm(case["defect_y_mm"])],
        "defect_depth:=", [mm(case["defect_depth_mm"])],
    ]


def export_options() -> list:
    return [
        "NAME:ExportOption",
        "IncludePtInOutput:=",
        True,
        "RefCSName:=",
        "Global",
        "PtInSI:=",
        False,
        "FieldInRefCS:=",
        True,
    ]


def export_named_b_expression(
    app: Maxwell3d,
    expression_name: str,
    output_file: Path,
    case: dict,
) -> None:
    reporter = app.ofieldsreporter
    reporter.CalcStack("clear")
    try:
        reporter.CopyNamedExprToStack(expression_name)
        reporter.ExportOnGrid(
            str(output_file),
            [mm(value) for value in B_GRID_START_MM],
            [mm(value) for value in B_GRID_STOP_MM],
            [mm(value) for value in B_GRID_STEP_MM],
            SOLUTION_NAME,
            variation_list(case),
            export_options(),
            "Cartesian",
            ["0mm", "0mm", "0mm"],
            False,
        )
    finally:
        reporter.CalcStack("clear")
    require(output_file.is_file() and output_file.stat().st_size > 100,
            f"AEDT did not create B field file {output_file}.")


def export_all_b_flds(app: Maxwell3d, case: dict, case_dir: Path) -> dict:
    files = {}
    for expression_name in NAMED_B_EXPRESSIONS:
        output_file = case_dir / f"{expression_name}.fld"
        export_named_b_expression(app, expression_name, output_file, case)
        files[expression_name] = output_file
    return files


def export_j_vector(
    app: Maxwell3d,
    case: dict,
    output_file: Path,
) -> None:
    reporter = app.ofieldsreporter
    reporter.CalcStack("clear")
    try:
        reporter.EnterQty(J_QUANTITY)
        reporter.ExportOnGrid(
            str(output_file),
            [mm(value) for value in J_GRID_START_MM],
            [mm(value) for value in J_GRID_STOP_MM],
            [mm(value) for value in J_GRID_STEP_MM],
            SOLUTION_NAME,
            variation_list(case),
            export_options(),
            "Cartesian",
            ["0mm", "0mm", "0mm"],
            False,
        )
    finally:
        reporter.CalcStack("clear")
    require(output_file.is_file() and output_file.stat().st_size > 100,
            f"AEDT did not create J vector file {output_file}.")


# =============================================================================
# Coordinate-safe FLD parsing and NPZ validation
# =============================================================================

def coordinate_indices(coordinates: np.ndarray, summary: dict):
    """Map Global-coordinate rows to regular-grid integer indices."""
    starts = summary["start_mm"]
    stops = summary["stop_mm"]
    steps = summary["step_mm"]
    counts = summary["shape_nx_ny_nz"]
    indices = []
    maximum_error = 0.0

    for axis in range(3):
        coordinate = coordinates[:, axis]
        require(np.isfinite(coordinate).all(),
                "FLD contains a non-finite point coordinate.")
        if counts[axis] == 1:
            index = np.zeros(coordinate.shape, dtype=np.int64)
            reconstructed = np.full(
                coordinate.shape, starts[axis], dtype=np.float64
            )
        else:
            index = np.rint(
                (coordinate - starts[axis]) / steps[axis]
            ).astype(np.int64)
            require(
                bool(np.all((index >= 0) & (index < counts[axis]))),
                "An FLD coordinate lies outside the requested grid.",
            )
            reconstructed = starts[axis] + index * steps[axis]
            require(
                bool(np.all(coordinate >= starts[axis] - 1e-6))
                and bool(np.all(coordinate <= stops[axis] + 1e-6)),
                "An FLD coordinate lies outside a grid endpoint.",
            )
        error = float(np.max(np.abs(coordinate - reconstructed)))
        maximum_error = max(maximum_error, error)
        indices.append(index)

    require(maximum_error <= 1e-6,
            f"FLD points miss the expected grid by {maximum_error:g} mm.")
    return indices[0], indices[1], indices[2], maximum_error


def find_numeric_grid_start(
    file_path: Path,
    minimum_columns: int,
    summary: dict,
    max_lines: int = 10_000,
) -> tuple[int, int] | None:
    """Locate the first numeric row whose coordinates lie on this grid."""
    with file_path.open("r", encoding="utf-8", errors="replace") as stream:
        for line_number, line in enumerate(stream, start=1):
            if line_number > max_lines:
                break
            tokens = line.replace(",", " ").replace("D", "E").split()
            if len(tokens) < minimum_columns:
                continue
            try:
                values = np.asarray([float(token) for token in tokens])
            except ValueError:
                continue
            try:
                coordinate_indices(values[:3].reshape(1, 3), summary)
            except RuntimeError:
                continue
            return line_number, len(tokens)
    return None


def parse_scalar_fld(
    fld_path: Path,
    summary: dict,
) -> tuple[np.ndarray, dict]:
    """Read x,y,z,value rows into [nz,ny,nx] without trusting row order."""
    require(fld_path.is_file() and fld_path.stat().st_size > 100,
            f"Missing or empty scalar FLD: {fld_path}")
    data_start = find_numeric_grid_start(fld_path, 4, summary)
    require(data_start is not None,
            f"Could not find x,y,z,value rows in {fld_path}.")
    first_line, column_count = data_start
    nx, ny, nz = summary["shape_nx_ny_nz"]
    point_count = summary["point_count"]
    output = np.empty(point_count, dtype=np.dtype(STORAGE_DTYPE))
    visited = np.zeros(point_count, dtype=np.uint8)
    row_count = 0
    max_coordinate_error = 0.0

    def process(lines: list[str]) -> None:
        nonlocal row_count, max_coordinate_error
        if not lines:
            return
        numeric_text = "\n".join(lines).replace(",", " ").replace("D", "E")
        values = np.fromstring(numeric_text, sep=" ", dtype=np.float64)
        expected = len(lines) * column_count
        require(values.size == expected,
                f"Malformed scalar rows near row {row_count + 1} in {fld_path}.")
        block = values.reshape(-1, column_count)
        ix, iy, iz, coordinate_error = coordinate_indices(block[:, :3], summary)
        max_coordinate_error = max(max_coordinate_error, coordinate_error)
        flat_index = (iz * ny + iy) * nx + ix
        require(np.unique(flat_index).size == flat_index.size,
                f"Duplicate scalar grid rows in one chunk: {fld_path}")
        require(not bool(np.any(visited[flat_index])),
                f"Duplicate scalar grid coordinates: {fld_path}")
        component = block[:, 3]
        require(np.isfinite(component).all(),
                f"Scalar FLD contains NaN or infinity: {fld_path}")
        output[flat_index] = component.astype(STORAGE_DTYPE, copy=False)
        visited[flat_index] = 1
        row_count += block.shape[0]

    with fld_path.open("r", encoding="utf-8", errors="replace") as stream:
        for _ in range(first_line - 1):
            next(stream)
        buffered = []
        for line in stream:
            stripped = line.strip()
            if not stripped:
                continue
            buffered.append(stripped)
            if len(buffered) >= FLD_PARSE_CHUNK_LINES:
                process(buffered)
                buffered.clear()
        process(buffered)

    require(row_count == point_count,
            f"{fld_path} has {row_count:,} rows; expected {point_count:,}.")
    require(int(np.count_nonzero(visited)) == point_count,
            f"{fld_path} did not fill every requested grid point.")
    return output.reshape(nz, ny, nx), {
        "source_fld_rows": row_count,
        "source_fld_numeric_columns": column_count,
        "max_coordinate_error_mm": max_coordinate_error,
    }


def validate_b_npz(npz_path: Path, summary: dict) -> dict:
    require(npz_path.is_file() and npz_path.stat().st_size > 100,
            f"B NPZ is missing or empty: {npz_path}")
    nx, ny, nz = summary["shape_nx_ny_nz"]
    require(nz == 1, "B validation expects exactly one scan plane.")
    expected_x, expected_y, expected_z = grid_axes(summary)
    with np.load(npz_path, allow_pickle=False) as archive:
        required = {"B", "x_mm", "y_mm", "z_mm", "components"}
        missing = required.difference(archive.files)
        require(not missing, f"B NPZ is missing arrays {sorted(missing)}.")
        B = archive["B"]
        require(B.shape == (3, ny, nx),
                f"Wrong B shape {B.shape}; expected {(3, ny, nx)}.")
        require(B.dtype == np.dtype(STORAGE_DTYPE),
                f"Wrong B dtype {B.dtype}.")
        require(list(archive["components"].astype(str)) == ["Bx", "By", "Bz"],
                "Wrong B component order.")
        require(np.allclose(archive["x_mm"], expected_x, rtol=0.0, atol=1e-9),
                "B x_mm does not match its grid.")
        require(np.allclose(archive["y_mm"], expected_y, rtol=0.0, atol=1e-9),
                "B y_mm does not match its grid.")
        require(np.allclose(archive["z_mm"], expected_z, rtol=0.0, atol=1e-9),
                "B z_mm does not match its scan plane.")
        require(np.isfinite(B).all(), "B tensor contains NaN or infinity.")
        max_abs = float(np.max(np.abs(B)))
        require(max_abs > 0.0, "B tensor is entirely zero.")
        nonzero = int(np.count_nonzero(B))
    return {
        "shape": [3, ny, nx],
        "dtype": STORAGE_DTYPE,
        "max_abs_B": max_abs,
        "nonzero_component_values": nonzero,
        "npz_size_MiB": npz_path.stat().st_size / 1024**2,
    }


def convert_b_flds_to_npz(
    fld_files: dict,
    npz_path: Path,
    case: dict,
) -> dict:
    component_arrays = []
    parser_statistics = {}
    for expression_name in NAMED_B_EXPRESSIONS:
        array_3d, statistics = parse_scalar_fld(
            fld_files[expression_name], B_GRID
        )
        require(array_3d.shape[0] == 1,
                "B scalar parser returned more than one Z plane.")
        component_arrays.append(array_3d[0])
        parser_statistics[expression_name] = statistics

    B = np.stack(component_arrays, axis=0).astype(STORAGE_DTYPE, copy=False)
    x_mm, y_mm, z_mm = grid_axes(B_GRID)
    partial_path = npz_path.with_name(npz_path.name + ".partial")
    if partial_path.exists():
        partial_path.unlink()
    validated = False
    try:
        with partial_path.open("wb") as stream:
            np.savez_compressed(
                stream,
                B=B,
                x_mm=x_mm,
                y_mm=y_mm,
                z_mm=z_mm,
                components=np.asarray(["Bx", "By", "Bz"]),
                field_unit=np.asarray("tesla"),
                coordinate_system=np.asarray("Global"),
                tensor_layout=np.asarray("[component,y,x]"),
                case_id=np.asarray(case["case_id"]),
                sampling_index=np.asarray(case["sampling_index"], dtype=np.int32),
                defect_x_mm=np.asarray(case["defect_x_mm"], dtype=np.float64),
                defect_y_mm=np.asarray(case["defect_y_mm"], dtype=np.float64),
                defect_depth_mm=np.asarray(
                    case["defect_depth_mm"], dtype=np.float64
                ),
            )
        partial_path.replace(npz_path)
        validation = validate_b_npz(npz_path, B_GRID)
        validation["fld_parser"] = parser_statistics
        validated = True
        return validation
    finally:
        if partial_path.exists():
            partial_path.unlink()
        if not validated and npz_path.exists():
            npz_path.unlink()


def validate_j_npz(npz_path: Path, summary: dict) -> dict:
    require(npz_path.is_file() and npz_path.stat().st_size > 100,
            f"J NPZ is missing or empty: {npz_path}")
    nx, ny, nz = summary["shape_nx_ny_nz"]
    expected_x, expected_y, expected_z = grid_axes(summary)
    with np.load(npz_path, allow_pickle=False) as archive:
        required = {
            "J",
            "x_mm",
            "y_mm",
            "z_mm",
            "depth_from_top_mm",
            "components",
        }
        missing = required.difference(archive.files)
        require(not missing, f"J NPZ is missing arrays {sorted(missing)}.")
        J = archive["J"]
        require(J.shape == (3, nz, ny, nx),
                f"Wrong J shape {J.shape}; expected {(3, nz, ny, nx)}.")
        require(J.dtype == np.dtype(STORAGE_DTYPE),
                f"Wrong J dtype {J.dtype}.")
        require(list(archive["components"].astype(str)) == ["Jx", "Jy", "Jz"],
                "Wrong J component order.")
        require(np.allclose(archive["x_mm"], expected_x, rtol=0.0, atol=1e-9),
                "J x_mm does not match its grid.")
        require(np.allclose(archive["y_mm"], expected_y, rtol=0.0, atol=1e-9),
                "J y_mm does not match its grid.")
        require(np.allclose(archive["z_mm"], expected_z, rtol=0.0, atol=1e-9),
                "J z_mm does not match its grid.")
        expected_depth = PCB_TOP_Z_MM - expected_z
        require(
            np.allclose(
                archive["depth_from_top_mm"],
                expected_depth,
                rtol=0.0,
                atol=1e-9,
            ),
            "J depth_from_top_mm is inconsistent with z_mm.",
        )
        require(np.isfinite(J).all(), "J tensor contains NaN or infinity.")
        max_abs = float(np.max(np.abs(J)))
        nonzero = int(np.count_nonzero(J))
        require(max_abs > 0.0 and nonzero > 0, "J tensor is entirely zero.")
    return {
        "shape": [3, nz, ny, nx],
        "dtype": STORAGE_DTYPE,
        "max_abs_J": max_abs,
        "nonzero_component_values": nonzero,
        "npz_size_MiB": npz_path.stat().st_size / 1024**2,
    }


def convert_j_fld_to_npz(
    fld_path: Path,
    npz_path: Path,
    case: dict,
) -> dict:
    """Stream x,y,z,Jx,Jy,Jz into a float32 [3,nz,ny,nx] NPZ."""
    require(fld_path.is_file() and fld_path.stat().st_size > 100,
            f"Missing or empty J FLD: {fld_path}")
    require(FLD_PARSE_CHUNK_LINES >= 1,
            "FLD_PARSE_CHUNK_LINES must be positive.")
    data_start = find_numeric_grid_start(fld_path, 6, J_GRID)
    require(data_start is not None,
            f"Could not find x,y,z,Jx,Jy,Jz rows in {fld_path}.")
    first_line, column_count = data_start
    nx, ny, nz = J_GRID["shape_nx_ny_nz"]
    point_count = J_GRID["point_count"]
    x_mm, y_mm, z_mm = grid_axes(J_GRID)

    tensor_temp = npz_path.with_name(npz_path.name + ".J.memmap")
    visited_temp = npz_path.with_name(npz_path.name + ".visited.memmap")
    partial_path = npz_path.with_name(npz_path.name + ".partial")
    for temporary in (tensor_temp, visited_temp, partial_path):
        if temporary.exists():
            temporary.unlink()

    J_map = None
    J_flat = None
    visited = None
    row_count = 0
    max_coordinate_error = 0.0
    nonfinite_replaced = 0
    validated = False
    try:
        J_map = np.memmap(
            tensor_temp,
            mode="w+",
            dtype=np.dtype(STORAGE_DTYPE),
            shape=(3, nz, ny, nx),
        )
        J_map[:] = 0.0
        J_flat = J_map.reshape(3, point_count)
        visited = np.memmap(
            visited_temp,
            mode="w+",
            dtype=np.uint8,
            shape=(point_count,),
        )
        visited[:] = 0

        def process(lines: list[str]) -> None:
            nonlocal row_count, max_coordinate_error, nonfinite_replaced
            if not lines:
                return
            numeric_text = "\n".join(lines).replace(",", " ").replace("D", "E")
            values = np.fromstring(numeric_text, sep=" ", dtype=np.float64)
            expected = len(lines) * column_count
            require(values.size == expected,
                    f"Malformed J rows near row {row_count + 1}.")
            block = values.reshape(-1, column_count)
            ix, iy, iz, coordinate_error = coordinate_indices(
                block[:, :3], J_GRID
            )
            max_coordinate_error = max(max_coordinate_error, coordinate_error)
            flat_index = (iz * ny + iy) * nx + ix
            require(np.unique(flat_index).size == flat_index.size,
                    "Duplicate J coordinates occur inside one FLD chunk.")
            require(not bool(np.any(visited[flat_index])),
                    "Duplicate J grid coordinates occur in the FLD.")
            J_values = block[:, 3:6]
            invalid = ~np.isfinite(J_values)
            nonfinite_replaced += int(np.count_nonzero(invalid))
            if np.any(invalid):
                J_values = np.nan_to_num(
                    J_values,
                    nan=0.0,
                    posinf=0.0,
                    neginf=0.0,
                    copy=True,
                )
            J_flat[:, flat_index] = J_values.T.astype(
                STORAGE_DTYPE, copy=False
            )
            visited[flat_index] = 1
            row_count += block.shape[0]

        with fld_path.open("r", encoding="utf-8", errors="replace") as stream:
            for _ in range(first_line - 1):
                next(stream)
            buffered = []
            for line in stream:
                stripped = line.strip()
                if not stripped:
                    continue
                buffered.append(stripped)
                if len(buffered) >= FLD_PARSE_CHUNK_LINES:
                    process(buffered)
                    buffered.clear()
            process(buffered)

        require(row_count == point_count,
                f"J FLD has {row_count:,} rows; expected {point_count:,}.")
        visited.flush()
        visited_points = int(np.count_nonzero(visited))
        require(visited_points == point_count,
                f"J FLD filled {visited_points:,}/{point_count:,} voxels.")
        J_map.flush()

        with partial_path.open("wb") as stream:
            np.savez_compressed(
                stream,
                J=J_map,
                x_mm=x_mm,
                y_mm=y_mm,
                z_mm=z_mm,
                depth_from_top_mm=PCB_TOP_Z_MM - z_mm,
                components=np.asarray(["Jx", "Jy", "Jz"]),
                field_unit=np.asarray("A/m^2"),
                coordinate_system=np.asarray("Global"),
                tensor_layout=np.asarray("[component,z,y,x]"),
                case_id=np.asarray(case["case_id"]),
                sampling_index=np.asarray(case["sampling_index"], dtype=np.int32),
                defect_x_mm=np.asarray(case["defect_x_mm"], dtype=np.float64),
                defect_y_mm=np.asarray(case["defect_y_mm"], dtype=np.float64),
                defect_depth_mm=np.asarray(
                    case["defect_depth_mm"], dtype=np.float64
                ),
            )
        partial_path.replace(npz_path)
        validation = validate_j_npz(npz_path, J_GRID)
        validation.update(
            {
                "source_fld_rows": row_count,
                "source_fld_numeric_columns": column_count,
                "nonfinite_values_replaced_with_zero": nonfinite_replaced,
                "max_coordinate_error_mm": max_coordinate_error,
            }
        )
        validated = True
        return validation
    finally:
        if J_flat is not None:
            del J_flat
        if J_map is not None:
            J_map.flush()
            del J_map
        if visited is not None:
            visited.flush()
            del visited
        for temporary in (tensor_temp, visited_temp, partial_path):
            if temporary.exists():
                temporary.unlink()
        if not validated and npz_path.exists():
            npz_path.unlink()


# =============================================================================
# Per-case metadata and run manifest
# =============================================================================

MANIFEST_COLUMNS = [
    "case_id",
    "sampling_index",
    "status",
    "defect_x_mm",
    "defect_y_mm",
    "defect_depth_mm",
    "B_npz",
    "J_npz",
    "B_tensor_shape",
    "J_tensor_shape",
    "B_npz_size_MiB",
    "J_npz_size_MiB",
    "temporary_J_fld_deleted",
    "elapsed_seconds",
    "error",
    "finished_at",
]


def append_manifest(row: dict) -> None:
    """Atomically insert or replace one case's latest status.

    A recovered case therefore replaces its earlier failed row instead of
    creating a duplicate failed/success pair in manifest.csv.
    """
    manifest_path = RUN_RESULT_DIR / "manifest.csv"
    partial_path = manifest_path.with_name(manifest_path.name + ".partial")
    existing_by_case = {}
    case_order = []
    if manifest_path.exists():
        with manifest_path.open(
            "r", newline="", encoding="utf-8-sig"
        ) as stream:
            for existing in csv.DictReader(stream):
                identifier = existing.get("case_id", "")
                if not identifier:
                    continue
                if identifier not in existing_by_case:
                    case_order.append(identifier)
                existing_by_case[identifier] = existing

    identifier = str(row.get("case_id", ""))
    require(identifier, "Manifest row has no case_id.")
    if identifier not in existing_by_case:
        case_order.append(identifier)
    existing_by_case[identifier] = {
        name: row.get(name, "") for name in MANIFEST_COLUMNS
    }

    if partial_path.exists():
        partial_path.unlink()
    with partial_path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=MANIFEST_COLUMNS)
        writer.writeheader()
        for case_id_value in case_order:
            writer.writerow(
                {
                    name: existing_by_case[case_id_value].get(name, "")
                    for name in MANIFEST_COLUMNS
                }
            )
    partial_path.replace(manifest_path)


def validate_npz_case_identity(npz_path: Path, case: dict) -> None:
    """Verify that a valid tensor belongs to this exact LHS sample."""
    with np.load(npz_path, allow_pickle=False) as archive:
        required = {
            "case_id",
            "sampling_index",
            "defect_x_mm",
            "defect_y_mm",
            "defect_depth_mm",
        }
        missing = required.difference(archive.files)
        require(
            not missing,
            f"{npz_path.name} is missing case identity arrays {sorted(missing)}.",
        )
        require(
            str(archive["case_id"].item()) == case["case_id"],
            f"{npz_path.name} belongs to a different case_id.",
        )
        require(
            int(archive["sampling_index"].item()) == case["sampling_index"],
            f"{npz_path.name} has a different sampling_index.",
        )
        for array_name in (
            "defect_x_mm",
            "defect_y_mm",
            "defect_depth_mm",
        ):
            require(
                math.isclose(
                    float(archive[array_name].item()),
                    case[array_name],
                    rel_tol=0.0,
                    abs_tol=1e-12,
                ),
                f"{npz_path.name} has a different {array_name}.",
            )


def archive_old_failure_marker(case_dir: Path) -> None:
    failure_path = case_dir / "case_failure.json"
    if not failure_path.is_file():
        return
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    archive_path = case_dir / f"case_failure_recovered_{timestamp}.json"
    failure_path.replace(archive_path)


def existing_case_is_complete(case_dir: Path, case: dict) -> bool:
    """Return True only after both NPZ tensors and their identities validate."""
    if not case_dir.is_dir():
        return False
    metadata_path = case_dir / "case_parameters.json"
    b_npz = case_dir / "B_2D_float32.npz"
    j_npz = case_dir / "J_3D_float32.npz"
    if not (b_npz.is_file() and j_npz.is_file()):
        return False

    try:
        b_validation = validate_b_npz(b_npz, B_GRID)
        j_validation = validate_j_npz(j_npz, J_GRID)
        validate_npz_case_identity(b_npz, case)
        validate_npz_case_identity(j_npz, case)
    except Exception as validation_error:
        print(
            f"{case['case_id']} exists but is incomplete/invalid and will be "
            f"rerun: {validation_error}"
        )
        return False

    # From this point onward the scientific B/J pair is complete.  Metadata,
    # manifest, or failure-marker repair must never turn it back into an
    # incomplete case (for example when manifest.csv is open in Excel).
    metadata = None
    if metadata_path.is_file():
        try:
            with metadata_path.open("r", encoding="utf-8") as stream:
                candidate_metadata = json.load(stream)
            require(
                candidate_metadata.get("run_id") == RUN_ID,
                "metadata has the wrong run_id.",
            )
            require(
                candidate_metadata.get("case_id") == case["case_id"],
                "metadata has the wrong case_id.",
            )
            old_defect = candidate_metadata.get("defect", {})
            for metadata_name, case_name in (
                ("x_mm", "defect_x_mm"),
                ("y_mm", "defect_y_mm"),
                ("centre_depth_from_pcb_top_mm", "defect_depth_mm"),
            ):
                require(
                    math.isclose(
                        float(old_defect[metadata_name]),
                        case[case_name],
                        rel_tol=0.0,
                        abs_tol=1e-12,
                    ),
                    f"metadata has a different {metadata_name}.",
                )
            metadata = candidate_metadata
        except Exception as metadata_error:
            print(
                f"Warning: {case['case_id']} tensor pair is valid, but "
                f"metadata will be repaired: {metadata_error}"
            )

    metrics = case_geometry_metrics(case)
    b_fld_files = {
        name: case_dir / f"{name}.fld"
        for name in NAMED_B_EXPRESSIONS
    }
    j_fld = case_dir / "J_vector_3D_temp.fld"
    try:
        elapsed = (
            float(metadata.get("elapsed_seconds", 0.0))
            if metadata is not None
            else 0.0
        )
    except (TypeError, ValueError):
        elapsed = 0.0

    if metadata is None:
        try:
            write_case_metadata(
                case_dir,
                case,
                metrics,
                b_fld_files,
                b_npz,
                b_validation,
                j_npz,
                j_validation,
                not j_fld.exists(),
                elapsed,
            )
        except Exception as metadata_write_error:
            print(
                f"Warning: valid tensors kept; metadata repair failed for "
                f"{case['case_id']}: {metadata_write_error}"
            )

    try:
        append_manifest(
            {
                **case,
                "status": "success",
                "B_npz": str(b_npz),
                "J_npz": str(j_npz),
                "B_tensor_shape": str(b_validation["shape"]),
                "J_tensor_shape": str(j_validation["shape"]),
                "B_npz_size_MiB": f"{b_validation['npz_size_MiB']:.3f}",
                "J_npz_size_MiB": f"{j_validation['npz_size_MiB']:.3f}",
                "temporary_J_fld_deleted": not j_fld.exists(),
                "elapsed_seconds": f"{elapsed:.3f}",
                "error": "",
                "finished_at": (
                    metadata.get("finished_at")
                    if metadata is not None
                    else datetime.now().isoformat(timespec="seconds")
                )
                or datetime.now().isoformat(timespec="seconds"),
            }
        )
    except Exception as manifest_error:
        print(
            f"Warning: valid tensors kept; manifest repair failed for "
            f"{case['case_id']}: {manifest_error}. Close manifest.csv in "
            "Excel before the next resume."
        )

    try:
        archive_old_failure_marker(case_dir)
    except OSError as marker_error:
        print(
            f"Warning: valid tensors kept; old failure marker could not be "
            f"archived for {case['case_id']}: {marker_error}"
        )
    return True


def prepare_incomplete_case_directory(case_dir: Path) -> None:
    """Remove only known, reproducible partial outputs from one failed case."""
    if not case_dir.exists():
        case_dir.mkdir(parents=True, exist_ok=False)
        return
    require(
        IS_RESUME_RUN and case_dir.is_dir(),
        f"Refusing to reuse an existing case path outside resume mode: {case_dir}",
    )
    try:
        archive_old_failure_marker(case_dir)
    except OSError as marker_error:
        print(
            f"Warning: old failure marker was kept in {case_dir.name}: "
            f"{marker_error}"
        )

    generated_names = [
        "smoothscalBx.fld",
        "smoothscalBy.fld",
        "smoothscalBz.fld",
        "B_2D_float32.npz",
        "B_2D_float32.npz.partial",
        "J_vector_3D_temp.fld",
        "J_3D_float32.npz",
        "J_3D_float32.npz.partial",
        "J_3D_float32.npz.J.memmap",
        "J_3D_float32.npz.visited.memmap",
        "case_parameters.json",
    ]
    removed = []
    for name in generated_names:
        path = case_dir / name
        if path.is_file():
            backup = case_dir / ("incomplete_backup_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
            backup.mkdir(exist_ok=False)
            path.replace(backup / name)
            removed.append(name)
    if removed:
        print(
            f"Backed up incomplete outputs (recoverable) in {case_dir.name}: "
            + ", ".join(removed)
        )


def write_case_metadata(
    case_dir: Path,
    case: dict,
    metrics: dict,
    b_fld_files: dict,
    b_npz: Path,
    b_validation: dict,
    j_npz: Path,
    j_validation: dict,
    temporary_j_fld_deleted: bool,
    elapsed_seconds: float,
) -> None:
    metadata = {
        "run_id": RUN_ID,
        "case_id": case["case_id"],
        "sampling": {
            "method": "maximin Latin hypercube",
            "seed": SAMPLING_SEED,
            "sampling_index": case["sampling_index"],
            "normalized_coordinates": [
                case["lhs_u_x"],
                case["lhs_u_y"],
                case["lhs_u_depth"],
            ],
        },
        "defect": {
            "shape": "straight rectangular copper bridge",
            "x_mm": case["defect_x_mm"],
            "y_mm": case["defect_y_mm"],
            "centre_depth_from_pcb_top_mm": case["defect_depth_mm"],
            "centre_z_global_mm": PCB_TOP_Z_MM - case["defect_depth_mm"],
            "dimensions_mm": [
                DEFECT_LENGTH_MM,
                DEFECT_WIDTH_MM,
                DEFECT_THICKNESS_MM,
            ],
            "connectivity_metrics": metrics,
        },
        "B": {
            "npz_file": b_npz.name,
            "raw_fld_files": {
                name: path.name for name, path in b_fld_files.items()
                if path.exists()
            },
            "components": ["Bx", "By", "Bz"],
            "field_unit": "tesla",
            "grid": B_GRID,
            "tensor_layout": "[component,y,x]",
            "validation": b_validation,
        },
        "J": {
            "npz_file": j_npz.name,
            "components": ["Jx", "Jy", "Jz"],
            "field_unit": "A/m^2",
            "grid": J_GRID,
            "tensor_layout": "[component,z,y,x]",
            "temporary_fld_deleted_after_validation":
                temporary_j_fld_deleted,
            "validation": j_validation,
        },
        "solution": SOLUTION_NAME,
        "elapsed_seconds": elapsed_seconds,
        "finished_at": datetime.now().isoformat(timespec="seconds"),
    }
    with (case_dir / "case_parameters.json").open(
        "w", encoding="utf-8"
    ) as stream:
        json.dump(metadata, stream, indent=2, ensure_ascii=False)


def write_case_failure(case_dir: Path, case: dict, error: Exception) -> None:
    payload = {
        "run_id": RUN_ID,
        "case": case,
        "status": "failed",
        "error": repr(error),
        "traceback": traceback.format_exc(),
        "finished_at": datetime.now().isoformat(timespec="seconds"),
    }
    with (case_dir / "case_failure.json").open(
        "w", encoding="utf-8"
    ) as stream:
        json.dump(payload, stream, indent=2, ensure_ascii=False)


# =============================================================================
# Solve all 100 cases and save paired B/J data
# =============================================================================

def solve_and_export_all_cases(app: Maxwell3d) -> None:
    total = len(CASES)
    skipped_count = 0
    for index, case in enumerate(CASES, start=1):
        case_dir = RUN_RESULT_DIR / case["case_id"]
        if IS_RESUME_RUN and existing_case_is_complete(case_dir, case):
            skipped_count += 1
            print(
                f"[{index}/{total}] {case['case_id']}: existing B/J NPZ pair "
                "fully validated; skipped."
            )
            continue

        prepare_incomplete_case_directory(case_dir)
        start_time = time.perf_counter()
        print(
            f"\n[{index}/{total}] {case['case_id']}: "
            f"x={case['defect_x_mm']:.6f} mm, "
            f"y={case['defect_y_mm']:.6f} mm, "
            f"depth={case['defect_depth_mm']:.6f} mm"
        )

        b_npz = case_dir / "B_2D_float32.npz"
        j_fld = case_dir / "J_vector_3D_temp.fld"
        j_npz = case_dir / "J_3D_float32.npz"
        try:
            set_case_variables(app, case)
            metrics = verify_case_straight_bridge(app, case)
            solved = app.analyze_setup(SETUP_NAME, cores=CORES)
            require(solved is not False,
                    f"AEDT reported that {SETUP_NAME} did not solve.")
            if SAVE_PROJECT_AFTER_EACH_CASE:
                require(app.save_project() is not False,
                        "Project save failed after the solved case.")

            b_fld_files = export_all_b_flds(app, case, case_dir)
            b_validation = convert_b_flds_to_npz(
                b_fld_files, b_npz, case
            )
            if DELETE_B_FLDS_AFTER_VERIFIED_NPZ:
                for fld_path in b_fld_files.values():
                    if fld_path.exists():
                        fld_path.unlink()

            export_j_vector(app, case, j_fld)
            j_validation = convert_j_fld_to_npz(j_fld, j_npz, case)
            temporary_j_fld_deleted = False
            if DELETE_TEMP_J_FLD_AFTER_VERIFIED_NPZ and j_fld.exists():
                try:
                    j_fld.unlink()
                    temporary_j_fld_deleted = True
                except OSError as deletion_error:
                    print(
                        "Warning: the verified J NPZ is valid, but the "
                        f"temporary FLD could not be removed: {deletion_error}"
                    )

            elapsed = time.perf_counter() - start_time
            write_case_metadata(
                case_dir,
                case,
                metrics,
                b_fld_files,
                b_npz,
                b_validation,
                j_npz,
                j_validation,
                temporary_j_fld_deleted,
                elapsed,
            )
            append_manifest(
                {
                    **case,
                    "status": "success",
                    "B_npz": str(b_npz),
                    "J_npz": str(j_npz),
                    "B_tensor_shape": str(b_validation["shape"]),
                    "J_tensor_shape": str(j_validation["shape"]),
                    "B_npz_size_MiB": f"{b_validation['npz_size_MiB']:.3f}",
                    "J_npz_size_MiB": f"{j_validation['npz_size_MiB']:.3f}",
                    "temporary_J_fld_deleted": temporary_j_fld_deleted,
                    "elapsed_seconds": f"{elapsed:.3f}",
                    "error": "",
                    "finished_at": datetime.now().isoformat(timespec="seconds"),
                }
            )
            print(
                f"Saved paired tensors: {b_npz.name} {b_validation['shape']}, "
                f"{j_npz.name} {j_validation['shape']}"
            )
        except Exception as exc:
            elapsed = time.perf_counter() - start_time
            write_case_failure(case_dir, case, exc)
            append_manifest(
                {
                    **case,
                    "status": "failed",
                    "B_npz": str(b_npz),
                    "J_npz": str(j_npz),
                    "elapsed_seconds": f"{elapsed:.3f}",
                    "temporary_J_fld_deleted": False,
                    "error": repr(exc),
                    "finished_at": datetime.now().isoformat(timespec="seconds"),
                }
            )
            print(f"Case failed: {exc}")
            traceback.print_exc()
            if not CONTINUE_ON_CASE_ERROR:
                raise

    if IS_RESUME_RUN:
        print(
            f"\nResume summary: {skipped_count} complete cases skipped; "
            f"{total - skipped_count} cases processed in this session."
        )


def run_workflow():
    check_configuration()
    if IS_RESUME_RUN:
        validate_existing_run_inputs()
    else:
        write_sampling_table()
        write_run_configuration()

    nx_b, ny_b, _ = B_GRID["shape_nx_ny_nz"]
    nx_j, ny_j, nz_j = J_GRID["shape_nx_ny_nz"]
    if IS_RESUME_RUN:
        print(f"Extending/resuming existing V2 run to {N_CASES} cases: {RUN_ID}")
        print(f"Existing AEDT project: {PROJECT_FILE}")
        print(f"Existing Result folder: {RUN_RESULT_DIR}")
    else:
        print(f"Creating a new 100-case V2 run: {RUN_ID}")
    print(f"B tensor per case: [3, {ny_b}, {nx_b}]")
    print(f"J tensor per case: [3, {nz_j}, {ny_j}, {nx_j}]")
    print(
        "Defect depth range: "
        f"{DEFECT_DEPTH_RANGE_MM[0]:g} ... "
        f"{DEFECT_DEPTH_RANGE_MM[1]:g} mm"
    )

    app = None
    try:
        if IS_RESUME_RUN:
            app = Maxwell3d(
                project=str(PROJECT_FILE),
                design=DESIGN_NAME,
                solution_type="Magnetostatic",
                version=AEDT_VERSION,
                non_graphical=NON_GRAPHICAL,
                new_desktop=True,
                close_on_exit=False,
                remove_lock=False,
            )
            require(
                app.valid_design,
                f"Could not open resume design {DESIGN_NAME!r}.",
            )
            app.modeler.model_units = "mm"
            required_objects = {PCB_NAME, CONDUCTOR_NAME, REGION_NAME}
            missing_objects = required_objects.difference(app.modeler.object_names)
            require(
                not missing_objects,
                f"Resume project is missing objects: {sorted(missing_objects)}",
            )
            require(
                SETUP_NAME in app.setup_names,
                f"Resume project has no setup {SETUP_NAME!r}.",
            )
            print(
                "Resume project opened and verified. Complete cases will be "
                "validated and skipped; the first incomplete case will be "
                "solved again before B/J export."
            )
        else:
            app = Maxwell3d(
                project=None,
                design=DESIGN_NAME,
                solution_type="Magnetostatic",
                version=AEDT_VERSION,
                non_graphical=NON_GRAPHICAL,
                new_desktop=True,
                close_on_exit=False,
                remove_lock=False,
            )
            require(app.valid_design, f"Could not create design {DESIGN_NAME!r}.")
            require(
                app.save_project(
                    str(PROJECT_FILE),
                    overwrite=False,
                    refresh_ids=True,
                ),
                f"Could not save the new project to {PROJECT_FILE}.",
            )

            build_model(app)
            require(app.save_project() is not False,
                    "Pre-solve project save failed.")

        if ANALYZE:
            solve_and_export_all_cases(app)
        else:
            print("ANALYZE=False: model and sample table built; no cases solved.")

        require(app.save_project() is not False, "Final project save failed.")
        if IS_RESUME_RUN:
            print("\nCompleted/resumed V2 dataset generation.")
        else:
            print("\nCompleted fresh V2 dataset generation.")
        print(f"AEDT project: {PROJECT_FILE}")
        print(f"Result directory: {RUN_RESULT_DIR}")
        return app
    except Exception:
        print("\nWorkflow stopped. Read the first red AEDT Message Manager error.")
        if app is not None and not CLOSE_AEDT_WHEN_DONE:
            print("AEDT was left open for inspection.")
        raise
    finally:
        if app is not None and CLOSE_AEDT_WHEN_DONE:
            app.release_desktop(close_projects=True, close_desktop=True)




# =============================================================================
# Safe extension entry point (reuses the proven solver/export functions above)
# =============================================================================
import argparse
import hashlib
import os
from contextlib import contextmanager

# 可直接按 Run，然后选旧 run_config.json；也可以在下面填写它的绝对路径。
# 若项目移了位置，可填真实 .aedt 路径；留空则使用 run_config 中的路径。
ORIGINAL_CASE_COUNT = 100
PROTECTED_COMPLETE_IDS = set()
CASE_COLUMNS = [
    "case_id", "sampling_index", "defect_x_mm", "defect_y_mm",
    "defect_depth_mm", "lhs_u_x", "lhs_u_y", "lhs_u_depth",
]
PARAM_COLUMNS = ["defect_x_mm", "defect_y_mm", "defect_depth_mm"]


def parameter_bounds():
    return np.array([
        DEFECT_X_RANGE_MM, DEFECT_Y_RANGE_MM, DEFECT_DEPTH_RANGE_MM
    ], dtype=np.float64).T


def read_case_table(path, expected_count):
    with Path(path).open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    require(len(rows) == expected_count,
            f"{path}: expected {expected_count} rows, found {len(rows)}.")
    lower, upper = parameter_bounds()
    cases = []
    for index, row in enumerate(rows, 1):
        require(row.get("case_id") == f"case_{index:04d}",
                f"{path}: wrong case_id at row {index}.")
        require(int(row["sampling_index"]) == index, "Sampling index mismatch.")
        case = {"case_id": row["case_id"], "sampling_index": index}
        xyz = np.array([float(row[k]) for k in PARAM_COLUMNS])
        require(np.isfinite(xyz).all(), "Nonfinite sample coordinate.")
        require(np.all(xyz >= lower) and np.all(xyz <= upper),
                f"{case['case_id']} lies outside original geometry ranges.")
        unit = (xyz - lower) / (upper - lower)
        case.update(zip(PARAM_COLUMNS, xyz.tolist()))
        # Copy old normalized coordinates if present; never regenerate old xyz.
        for column, value in zip(CASE_COLUMNS[5:], unit):
            case[column] = float(row[column]) if row.get(column) else float(value)
        cases.append(case)
    return cases


def assert_same_cases(actual, expected):
    require(len(actual) == len(expected), "Case table length changed.")
    for a, b in zip(actual, expected):
        require(a["case_id"] == b["case_id"] and
                a["sampling_index"] == b["sampling_index"],
                "Case ID/index changed.")
        for key in PARAM_COLUMNS:
            require(math.isclose(a[key], b[key], rel_tol=0, abs_tol=1e-12),
                    f"{a['case_id']}: coordinate changed: {key}.")


def normalized_points(cases):
    lower, upper = parameter_bounds()
    return (np.array([[c[k] for k in PARAM_COLUMNS] for c in cases])
            - lower) / (upper - lower)


def augment_fixed_cases(original, total, seed):
    """Append a deterministic LHS batch; preserve every supplied old point.

    Combined batches are not claimed to form a single Latin hypercube.
    """
    count = total - len(original)
    require(count > 0, "Target must exceed the original case count.")
    old_unit = normalized_points(original)
    rng = np.random.default_rng(np.random.SeedSequence([seed, len(original), total]))
    best, best_score = None, -1.0
    for _ in range(LHS_CANDIDATE_COUNT):
        unit = np.column_stack([
            (rng.permutation(count) + rng.random(count)) / count
            for _ in range(3)
        ])
        old_d2 = np.sum((unit[:, None, :] - old_unit[None, :, :]) ** 2, axis=2)
        new_d2 = np.sum((unit[:, None, :] - unit[None, :, :]) ** 2, axis=2)
        np.fill_diagonal(new_d2, np.inf)
        score = min(float(old_d2.min()), float(new_d2.min()))
        if score > best_score:
            best, best_score = unit.copy(), score
    require(best is not None and best_score > 1e-20,
            "Failed to obtain distinct additional positions.")
    lower, upper = parameter_bounds()
    physical = lower + best * (upper - lower)
    cases = [dict(c) for c in original]
    for offset, xyz in enumerate(physical):
        index = len(original) + offset + 1
        c = {"case_id": f"case_{index:04d}", "sampling_index": index}
        c.update(zip(PARAM_COLUMNS, xyz.tolist()))
        c.update(zip(CASE_COLUMNS[5:], best[offset].tolist()))
        cases.append(c)
    return cases, math.sqrt(best_score)


def validate_no_duplicate_coordinates(cases):
    points = normalized_points(cases)
    distance = np.sum((points[:, None, :] - points[None, :, :]) ** 2, axis=2)
    np.fill_diagonal(distance, np.inf)
    require(float(distance.min()) > 1e-20,
            "Duplicate or numerically indistinguishable sample positions.")


def json_read(path):
    with Path(path).open("r", encoding="utf-8-sig") as stream:
        return json.load(stream)


def assert_configuration_matches(old):
    """Reject geometry/grid/solver differences rather than silently mix datasets."""
    expected = configuration_dictionary()
    for section in ("geometry_mm", "excitation", "mesh_and_solver"):
        require(old.get(section) == expected[section],
                f"Original {section} differs from recovered V2 defaults. "
                "STOP: send the original run_config.json to adapt this script.")
    for field in ("B_export", "J_export"):
        for key in ("grid", "components", "tensor_layout", "storage_dtype"):
            require(old.get(field, {}).get(key) == expected[field][key],
                    f"Original {field}.{key} differs. No existing data changed.")
    require(old.get("sampling", {}).get("ranges_mm") ==
            expected["sampling"]["ranges_mm"], "Sampling ranges differ.")
    require(old.get("sampling", {}).get("case_count") == ORIGINAL_CASE_COUNT,
            "Select the ORIGINAL 100-case run_config.json.")
    require(old.get("software", {}).get("solver") == "Maxwell 3D Magnetostatic",
            "Unexpected solver type.")


def validate_existing_run_inputs():
    # run_workflow invokes this again before opening the existing project.
    assert_configuration_matches(json_read(RUN_RESULT_DIR / "run_config.json"))
    old = read_case_table(RUN_RESULT_DIR / "sampling_100_cases.csv", 100)
    assert_same_cases(CASES[:100], old)


def existing_case_is_complete(case_dir, case):
    # Read-only preflight has already fully loaded and validated every NPZ pair.
    # Do not repair metadata or rewrite manifests for complete old cases.
    return case["case_id"] in PROTECTED_COMPLETE_IDS


def preflight_pairs():
    PROTECTED_COMPLETE_IDS.clear()
    for index, case in enumerate(CASES, 1):
        folder = RUN_RESULT_DIR / case["case_id"]
        b = folder / "B_2D_float32.npz"
        j = folder / "J_3D_float32.npz"
        try:
            validate_b_npz(b, B_GRID)
            validate_j_npz(j, J_GRID)
            validate_npz_case_identity(b, case)
            validate_npz_case_identity(j, case)
        except Exception as exc:
            if index <= ORIGINAL_CASE_COUNT:
                raise RuntimeError(
                    f"Protected original {case['case_id']} is missing/invalid: {exc}. "
                    "STOP: no original B/J will be deleted or re-solved."
                ) from exc
            # Even partial existing new cases must not belong to another coordinate.
            # Readable wrong-identity NPZs stop instead of being overwritten.
            for path in (b, j):
                if path.is_file():
                    try:
                        with np.load(path, allow_pickle=False) as archive:
                            identity = {
                                k: archive[k].item()
                                for k in ("case_id", "sampling_index", *PARAM_COLUMNS)
                            }
                    except (OSError, ValueError, KeyError, EOFError):
                        continue  # incomplete file; moved to backup before re-solve
                    require(identity["case_id"] == case["case_id"] and
                            int(identity["sampling_index"]) == index,
                            f"{path}: readable identity mismatch; stopped.")
                    for key in PARAM_COLUMNS:
                        require(math.isclose(float(identity[key]), case[key],
                                             rel_tol=0, abs_tol=1e-12),
                                f"{path}: existing coordinates differ; stopped.")
            print(f"[CHECK {index}/{N_CASES}] {case['case_id']}: pending/incomplete.")
        else:
            PROTECTED_COMPLETE_IDS.add(case["case_id"])
            print(f"[CHECK {index}/{N_CASES}] {case['case_id']}: B/J validated; SKIP.",
                  flush=True)


def load_fixed_200(original_path):
    old100 = read_case_table(original_path, 100)
    prior_table = RUN_RESULT_DIR / "sampling_200_cases.csv"
    prior_info = RUN_RESULT_DIR / "extension_200_config.json"
    require(prior_table.is_file() and prior_info.is_file(),
            "The saved sampling_200_cases.csv and extension_200_config.json are required. "
            "Restore them; existing case coordinates must never be regenerated.")
    fixed = read_case_table(prior_table, 200)
    assert_same_cases(fixed[:100], old100)
    metadata = json_read(prior_info)
    require(metadata.get("target_case_count") == 200 and
            metadata.get("root_seed") == SAMPLING_SEED,
            "Previous 200-case metadata count/seed mismatch.")
    for key, path in (("original_table_sha256", original_path),
                      ("extended_table_sha256", prior_table)):
        require(metadata.get(key) == hashlib.sha256(path.read_bytes()).hexdigest(),
                f"Previous sampling table was changed: {path}")
    validate_no_duplicate_coordinates(fixed)
    return fixed


def extension_payload(table, original_path, score):
    return {
        "run_id": RUN_ID,
        "original_case_count": 100,
        "preserved_planned_case_count": 200,
        "target_case_count": TARGET_CASE_COUNT,
        "root_seed": SAMPLING_SEED,
        "seed_substream": [SAMPLING_SEED, 200, TARGET_CASE_COUNT],
        "method": "fixed saved 200 points + conditional maximin 100-point LHS batch",
        "combined_is_single_300_point_LHS": False,
        "candidate_count": LHS_CANDIDATE_COUNT,
        "new_to_old_and_new_min_normalized_distance": score,
        "original_table_sha256": hashlib.sha256(original_path.read_bytes()).hexdigest(),
        "preserved_200_table_sha256": hashlib.sha256(
            (RUN_RESULT_DIR / "sampling_200_cases.csv").read_bytes()).hexdigest(),
        "extended_table_sha256": hashlib.sha256(table.read_bytes()).hexdigest(),
        "project_file": str(PROJECT_FILE),
        "result_directory": str(RUN_RESULT_DIR),
        "existing_complete_B_J_policy": "validate and skip; no data rewrites",
    }


def verify_extension_metadata(table, original_path):
    metadata = json_read(RUN_RESULT_DIR / "extension_300_config.json")
    expected = extension_payload(table, original_path,
        float(metadata["new_to_old_and_new_min_normalized_distance"]))
    for key in ("run_id", "preserved_planned_case_count", "target_case_count",
                "root_seed", "seed_substream", "candidate_count",
                "original_table_sha256", "preserved_200_table_sha256",
                "extended_table_sha256"):
        require(metadata.get(key) == expected[key],
                f"300-case extension metadata mismatch: {key}")
    return float(metadata["new_to_old_and_new_min_normalized_distance"])


def save_extension_plan(table, original_path, score):
    # Persist the plan BEFORE solving; old 100/200 tables and metadata stay intact.
    if not table.exists():
        partial = table.with_name(table.name + ".partial")
        with partial.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=CASE_COLUMNS)
            writer.writeheader()
            writer.writerows(CASES)
        os.replace(partial, table)
    info = RUN_RESULT_DIR / "extension_300_config.json"
    if info.exists():
        verify_extension_metadata(table, original_path)
    else:
        partial = info.with_name(info.name + ".partial")
        with partial.open("w", encoding="utf-8") as stream:
            json.dump(extension_payload(table, original_path, score), stream, indent=2)
        os.replace(partial, info)


@contextmanager
def extension_lock():
    # Shared with the old 200-case runner, intentionally NOT renamed to 300.
    path = RUN_RESULT_DIR / "extension_200.running.lock"
    try:
        stream = path.open("x", encoding="utf-8")
    except FileExistsError as exc:
        raise RuntimeError(
            f"Another extension may be running: {path}. "
            "If a prior Python process crashed, FIRST confirm it and its AEDT "
            "job have stopped, then manually remove ONLY this lock file."
        ) from exc
    try:
        with stream:
            stream.write(f"pid={os.getpid()}\nstarted={datetime.now().isoformat()}\n")
        yield
    finally:
        path.unlink(missing_ok=True)


def choose_config_path(raw):
    if raw:
        return Path(raw).expanduser().resolve()
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    try:
        selected = filedialog.askopenfilename(
            title="Select ORIGINAL run_config.json (inside old Result/run_...)",
            filetypes=[("Run configuration", "*.json")])
    finally:
        root.destroy()
    require(bool(selected), "No run_config.json selected; nothing changed.")
    return Path(selected).resolve()


def extension_main():
    global RUN_RESULT_DIR, PROJECT_FILE, BASE_DIR, RESULT_ROOT, RUN_ID
    global IS_RESUME_RUN, RESUME_RUN_ID, N_CASES, CASES, SAMPLING_SEED
    global LHS_MIN_NORMALIZED_DISTANCE, LHS_CANDIDATE_COUNT, Maxwell3d
    parser = argparse.ArgumentParser(
        description="Resume V2 to 300 cases; preserve all 200 planned coordinates.")
    parser.add_argument("--config", default=EXISTING_RUN_CONFIG,
                        help="Original run_config.json; omitted = file selection dialog.")
    parser.add_argument("--project", default=EXISTING_PROJECT_FILE,
                        help="Existing AEDT project override if it was moved.")
    parser.add_argument("--check-only", action="store_true",
                        help="Validate original data/plan without writes or starting Ansys.")
    args = parser.parse_args()
    config_path = choose_config_path(args.config)
    require(config_path.name == "run_config.json" and config_path.is_file(),
            "Select the original file named run_config.json.")
    old = json_read(config_path)
    RUN_RESULT_DIR = config_path.parent
    RESULT_ROOT = RUN_RESULT_DIR.parent
    RUN_ID = str(old["run_id"])
    require(RUN_ID and "/" not in RUN_ID and "\\" not in RUN_ID, "Invalid run_id.")
    RESUME_RUN_ID = RUN_ID
    IS_RESUME_RUN = True  # Never start a fresh run implicitly.
    N_CASES = TARGET_CASE_COUNT
    require(N_CASES == 300, "This extension preserves the 200-case plan and targets 300.")
    SAMPLING_SEED = int(old["sampling"]["seed"])
    LHS_CANDIDATE_COUNT = int(old["sampling"]["candidate_count"])
    require(LHS_CANDIDATE_COUNT >= 1, "Invalid candidate_count.")
    raw_project = args.project or old["project_file"]
    PROJECT_FILE = Path(raw_project).expanduser()
    if not PROJECT_FILE.is_absolute():
        PROJECT_FILE = config_path.parent / PROJECT_FILE
    if not PROJECT_FILE.is_file() and not args.project:
        # Standard layout after moving an entire V2 tree to a different disk.
        candidate = RESULT_ROOT.parent / f"Deep_Defect_Dataset_V2_{RUN_ID}.aedt"
        if candidate.is_file():
            PROJECT_FILE = candidate
    PROJECT_FILE = PROJECT_FILE.resolve()
    require(PROJECT_FILE.is_file(),
            f"Existing .aedt project missing: {PROJECT_FILE}. "
            "Use --project with its actual path. No new model will be silently built.")
    BASE_DIR = PROJECT_FILE.parent
    assert_configuration_matches(old)
    original_path = RUN_RESULT_DIR / "sampling_100_cases.csv"
    fixed = load_fixed_200(original_path)
    table = RUN_RESULT_DIR / "sampling_300_cases.csv"
    info = RUN_RESULT_DIR / "extension_300_config.json"

    def prepare_and_check():
        global CASES, LHS_MIN_NORMALIZED_DISTANCE
        if table.exists():
            CASES = read_case_table(table, N_CASES)
            assert_same_cases(CASES[:200], fixed)
            if info.exists():
                LHS_MIN_NORMALIZED_DISTANCE = verify_extension_metadata(table, original_path)
            else:
                # Recover a crash between table and metadata writes by comparison only.
                expected, score = augment_fixed_cases(fixed, N_CASES, SAMPLING_SEED)
                assert_same_cases(CASES, expected)
                LHS_MIN_NORMALIZED_DISTANCE = score
        else:
            require(not info.exists(), "300-case table missing but metadata exists; stop.")
            require(not any((RUN_RESULT_DIR / f"case_{i:04d}").exists()
                            for i in range(201, N_CASES + 1)),
                    "Cases 201-300 exist but sampling_300_cases.csv is missing. "
                    "Restore the table; coordinates will not be guessed.")
            CASES, LHS_MIN_NORMALIZED_DISTANCE = augment_fixed_cases(
                fixed, N_CASES, SAMPLING_SEED)
        validate_no_duplicate_coordinates(CASES)
        # Pure geometry checks occur in check_configuration before Ansys.
        # All bounds were validated by table loading / augmentation above.
        preflight_pairs()
        print(f"\nOriginal folder: {RUN_RESULT_DIR}")
        print(f"Existing project: {PROJECT_FILE}")
        print(f"Root seed: {SAMPLING_SEED}; target sample count: {N_CASES}")
        print(f"Verified complete: {len(PROTECTED_COMPLETE_IDS)}; "
              f"pending: {N_CASES-len(PROTECTED_COMPLETE_IDS)}")

    if args.check_only:
        prepare_and_check()
        print("CHECK ONLY passed. No files written and Ansys not started.")
        return

    with extension_lock():
        prepare_and_check()
        check_configuration()
        save_extension_plan(table, original_path, LHS_MIN_NORMALIZED_DISTANCE)
        if len(PROTECTED_COMPLETE_IDS) == N_CASES:
            print(f"All {N_CASES} B/J pairs complete. Nothing to solve; Ansys not started.")
            return
        project_lock = Path(str(PROJECT_FILE) + ".lock")
        require(not project_lock.exists(),
                f"V2 project is open/locked: {PROJECT_FILE}. Close the AEDT window "
                "for THIS V2 project, then rerun. Do not delete the .aedt.lock file.")
        from ansys.aedt.core import Maxwell3d
        run_workflow()


if __name__ == "__main__":
    extension_main()
