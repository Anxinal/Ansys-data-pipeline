"""Settings shared across the project. Lengths are in the design's model units."""

from pathlib import Path

# --- Run (main.py takes no command-line options; edit these instead) ---
DEFAULT_INPUT_PATH = "E:/An Xiao/data/L4321_M16.aedt"  # the .aedt project to open
DESIGN = None  # design to open; None for the project's active design
SHOW_INFO = False  # also print everything the project can tell about itself
SHOW_DESKTOP = False  # show the AEDT desktop, and leave it and the project open afterwards
# What main.py does:
#   "analyse"   solve the design and export Bz above its board
#   "extract"   copy the board, spheres and GND/VCC into a new group (DEFAULT_PREFIX<n>), then analyse that copy
#   "copy"      analyse the existing copy COPY_GROUP
#   "sections"  extract every section listed in SECTIONS_FILE (CSV or "board = ... Sphere_positions = ..." lines)
RUN_MODE = "analyse"
COPY_GROUP = ""  # for "copy", e.g. "BOARD_1"
SECTIONS_FILE = ""  # for "sections"
EXTRACT_ONLY = False  # "extract"/"sections": save the copies without validation, solving or field export
PURGE_HISTORY = False  # "extract"/"sections": purge the new copies' modeling history; freezes their geometry
REBUILD = False  # "copy"/"extract": recreate the copy's analysis design if it exists
BOARD = None  # the board to analyse; needed when the design has several
CORES = None  # cores for the solve; None for AEDT's default
SOLVE = True  # False reuses the setup's existing solution

# --- Bz analysis (Analysis.py) ---
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent / "Result" / "Bz"
DEFAULT_SETUP = "Setup1"
DEFAULT_SCAN_HEIGHT = 0.060  # image plane height above the board's top face
DEFAULT_GRID_STEP = 0.030  # image pixel size; also the Position grid step
# Fields-calculator named expression for the smoothed z-component of B;
# BzAnalysis creates it in the project when it is missing.
BZ_EXPRESSION = "smoothscalBz"

# Fields-calculator expressions Session.get_session_info checks for. AEDT can
# check a named expression by name but has no call that lists them all.
NAMED_EXPRESSIONS = (BZ_EXPRESSION,)

# --- Chip model (Chips/) ---
# Names of the GND and VCC components or excitations and of the two connection spheres.
DEFAULT_GND = "GND"
DEFAULT_VCC = "VCC"
DEFAULT_SPEHRE = ["Sphere_GND", "Sphere_VCC"]
# Name fragments (case-insensitive) used to find the board, and the spheres when
# their geometry alone doesn't pick out exactly two.
BOARD_KEYWORDS = ("board", "pcb")
SPHERE_KEYWORDS = ("sphere", "ball")

# Materials that fill the air box around the model, never a chip part.
BACKGROUND_MATERIALS = {"vacuum", "air"}

# AEDT model-tree groups that give an object's type (Chips/Components/DesignCache.py).
TYPE_GROUPS = {"Solids": "Solid", "Sheets": "Sheet", "Lines": "Line"}

# --- Position sampling (Chips/Positions/PositionSampler.py) ---
SAMPLER_SEED = 0  # seed of the sampler's random generator; None for a different run each time

# Largest column number in position labels such as "A15" (NumericalPositionFixed.from_string);
# also the grid width of the pin count. Must match the design's xballcount variable.
MAX_COLUMN = 20

# --- Pin-count placement (AnsysSession/Action/SetTerminalPositions.py) ---
# Design variables holding the ball each terminal sits on, counted row by row from 0
# (Position.num). The terminal and its sphere follow them through the design's expressions.
PIN_COUNT_VARIABLES = {"VCC": "PinCount", "GND": "PinCountGND"}

# --- Extraction (Extract.py) ---
DEFAULT_PREFIX = "BOARD_"  # copies go to groups BOARD_1, BOARD_2, ...

# Duplication needs a non-zero vector; parts that stay in place are duplicated
# this far along x and moved straight back.
IN_PLACE_OFFSET = [1.0, 0.0, 0.0]

EXPORT_DATA_FOLDER = "/data"

# For CNN image clipping in no. of pixels
GRID_SIZE = []

# How far (0-255, per colour channel) a pixel of an AEDT model picture may differ from the
# background and still count as background (ImageData/BoardImage.py's crop_to_content).
BACKGROUND_TOLERANCE = 30
