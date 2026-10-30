"""Tests of BoardImage, BoardCell and BoardImageDataset on generated images; no AEDT needed."""

import os
import tempfile
import unittest

import numpy as np
from PIL import Image

from ImageData.BoardImage import BoardCell, BoardImage, crop_to_content


def board(name="Board", columns=6, rows=4, cell=10):
    """A board image whose pixels encode their own position, cut into columns x rows cells of cell x cell pixels."""
    pixels = np.arange(rows * cell * columns * cell * 3, dtype=np.uint32).reshape(rows * cell, columns * cell, 3) % 251
    return BoardImage(Image.fromarray(pixels.astype(np.uint8)), (cell, cell), columns - 1, rows - 1, name=name)


class BoardImageTests(unittest.TestCase):
    def test_split_all_is_row_by_row_with_the_right_pixels(self):
        image = board()
        cells = image.split_all()
        self.assertEqual(len(cells), 24)
        self.assertEqual([(c.x, c.y) for c in cells[:7]], [(0, 0), (1, 0), (2, 0), (3, 0), (4, 0), (5, 0), (0, 1)])
        cell = image.cell(2, 1)
        self.assertIsInstance(cell, BoardCell)
        self.assertEqual(cell.name, "Board_2_1")
        np.testing.assert_array_equal(np.asarray(cell.image), np.asarray(image.image)[10:20, 20:30])

    def test_cell_outside_the_grid_is_rejected(self):
        for x, y in [(6, 0), (0, 4), (-1, 0)]:
            with self.assertRaises(ValueError):
                board().cell(x, y)

    def test_grid_must_fit_the_image(self):
        image = Image.new("RGB", (60, 40))
        with self.assertRaisesRegex(ValueError, "doesn't fit"):
            BoardImage(image, (10, 10), 6, 3)
        with self.assertRaisesRegex(ValueError, "smaller than one"):
            BoardImage(image, (100, 100), -1, -1)

    def test_crop_to_content_puts_the_board_at_the_origin(self):
        pixels = np.linspace(200, 255, 50)[:, None, None] * np.ones((1, 80, 3))  # vertical gradient
        pixels[10:30, 20:55] = [40, 120, 40]
        cropped = crop_to_content(Image.fromarray(pixels.astype(np.uint8)))
        self.assertEqual(cropped.size, (35, 20))


class BoardImageDatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import torch  # noqa: F401
        except ImportError:
            raise unittest.SkipTest("torch is not installed")

    def labels(self, text):
        handle = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False)
        with handle:
            handle.write(text)
        self.addCleanup(os.unlink, handle.name)
        return handle.name

    def test_labels_from_file_and_tensor_format(self):
        from torch.utils.data import DataLoader
        from ImageData.BoardImageDataset import BoardImageDataset

        dataset = BoardImageDataset([board(), board("BOARD_1_Board")],
                                    self.labels("# positives\nBoard_2_1\n\nBOARD_1_Board_4_3\n"))
        self.assertEqual(len(dataset), 48)
        self.assertEqual(dataset.labels.sum().item(), 2)
        self.assertAlmostEqual(dataset.pos_weight().item(), 23.0)
        index = [c.name for c in dataset.cells].index("Board_2_1")
        image, label = dataset[index]
        self.assertEqual((tuple(image.shape), label.item()), ((3, 10, 10), 1.0))
        self.assertLessEqual(image.max().item(), 1.0)
        images, labels = next(iter(DataLoader(dataset, batch_size=8)))
        self.assertEqual((tuple(images.shape), tuple(labels.shape)), ((8, 3, 10, 10), (8,)))

    def test_boards_and_cells_can_be_mixed(self):
        from ImageData.BoardImageDataset import BoardImageDataset

        dataset = BoardImageDataset([board(), *board("Other").split_all()], ["Other_5_3"])
        self.assertEqual((len(dataset), dataset.labels.sum().item()), (48, 1))

    def test_unknown_positive_and_duplicate_board_names_are_rejected(self):
        from ImageData.BoardImageDataset import BoardImageDataset

        with self.assertRaisesRegex(ValueError, "match no cell"):
            BoardImageDataset([board()], ["Board_9_9"])
        with self.assertRaisesRegex(ValueError, "share a name"):
            BoardImageDataset([board(), board()], [])


if __name__ == "__main__":
    unittest.main()
