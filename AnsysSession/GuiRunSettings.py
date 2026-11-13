"""Prepare a separate output folder and settings for a GUI-enabled J run."""
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import configs
from main import check_settings


def prepare(board, pins):
    if not board or any(c.isspace() for c in board):
        raise ValueError('BOARD must be a single component name')
    if len(set(pins)) < 2 or any(not isinstance(pin, int) or pin < 0 for pin in pins):
        raise ValueError('PINS needs at least two different nonnegative integer pin counts')
    stamp = datetime.now(timezone(timedelta(hours=8))).strftime('%Y%m%d_%H%M%S_%f')
    run_root = Path(configs.DEFAULT_OUTPUT_DIR).resolve()/f'J_GUI_{stamp}'
    output = run_root/'J'
    temp = output/'temp'
    temp.mkdir(parents=True, exist_ok=True)
    os.environ.update(TEMP=str(temp), TMP=str(temp), PYAEDT_USE_PRE_GRPC_ARGS='True',
                      PYAEDT_NON_GRAPHICAL='False')
    instructions = output/'input.txt'
    instructions.write_text(f'board = {board} Sphere_positions = {" ".join(map(str,pins))}\n')
    values = {name:getattr(configs,name) for name in dir(configs) if name.isupper()}
    values.update(RUN_MODE='sections', FIELD_QUANTITY='J', SHOW_DESKTOP=True,
                  SECTIONS_FILE=str(instructions), DEFAULT_OUTPUT_DIR=run_root)
    settings = SimpleNamespace(**values)
    check_settings(settings)
    return settings, output
