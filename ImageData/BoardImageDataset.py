"""Binary-classification dataset of board grid cells: can VCC/GND attach to the cell?"""

from pathlib import Path

import numpy as np
import torch
from torch.utils.data import Dataset

from .BoardImage import BoardCell, BoardImage


def read_label_names(path):
    """The cell names in a label file: one per line; blank lines and lines starting with # are skipped."""
    lines = (line.strip() for line in Path(path).read_text().splitlines())
    return {line for line in lines if line and not line.startswith("#")}


class BoardImageDataset(Dataset):
    """Every grid cell of ``boards`` as one sample: (image [3, H, W] float32 in 0..1, label 1.0 or 0.0).

    ``boards`` may mix whole BoardImages, which are split into their cells (split_all),
    and BoardCells already split. ``positives`` names the cells VCC/GND can attach to, as a
    label.txt path or a list of names; every other cell is negative. A cell's name is
    BoardImage.cell_name(x, y), e.g. "Board_3_5". ``transform``, if given, is applied
    to each image tensor.
    """

    def __init__(self, boards: list[BoardImage | BoardCell], positives, transform=None):
        positives = read_label_names(positives) if isinstance(positives, (str, Path)) else set(positives)
        self.cells = [cell for board in boards
                      for cell in ([board] if isinstance(board, BoardCell) else board.split_all())]
        names = [cell.name for cell in self.cells]
        if len(set(names)) != len(names):
            raise ValueError("Two boards share a name, so their cells can't be told apart")
        unknown = positives.difference(names)
        if unknown:
            raise ValueError(f"Positive names that match no cell: {sorted(unknown)}")
        self.labels = torch.tensor([name in positives for name in names], dtype=torch.float32)
        self.transform = transform

    def __len__(self):
        return len(self.cells)

    def __getitem__(self, index):
        pixels = np.asarray(self.cells[index].image.convert("RGB"), dtype=np.float32) / 255
        image = torch.from_numpy(pixels).permute(2, 0, 1)  # HWC -> CHW
        if self.transform:
            image = self.transform(image)
        return image, self.labels[index]

    def pos_weight(self):
        """Negatives per positive, for BCEWithLogitsLoss(pos_weight=...): positives are only a few cells."""
        positives = self.labels.sum()
        return (len(self.labels) - positives) / positives.clamp(min=1)
