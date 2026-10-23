"""Settings shared across the project. Lengths are in the design's model units."""

from pathlib import Path

# --- Bz analysis (Analysis.py); main.py's options override these per run ---
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
# Default names of the GND and VCC components or excitations (main.py's --gnd/--vcc).
DEFAULT_GND = "GND"
DEFAULT_VCC = "VCC"

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

# Largest column number in position labels such as "A15" (Position.from_string).
MAX_COLUMN = 20

# --- Extraction (Extract.py) ---
DEFAULT_PREFIX = "BOARD_"  # copies go to groups BOARD_1, BOARD_2, ...

# Duplication needs a non-zero vector; parts that stay in place are duplicated
# this far along x and moved straight back.
IN_PLACE_OFFSET = [1.0, 0.0, 0.0]

EXPORT_DATA_FOLDER = "/data"