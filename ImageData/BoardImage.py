import numpy as np
from PIL import Image

from configs import BACKGROUND_TOLERANCE


def crop_to_content(image: Image.Image, tolerance=BACKGROUND_TOLERANCE, return_box=False):
    """``image`` cut down to what differs from its background, so the content starts at pixel (0, 0).

    The background is taken from each row's leftmost pixel, which also covers
    AEDT's default top-to-bottom background gradient.
    """
    pixels = np.asarray(image.convert("RGB"), dtype=np.int16)
    content = np.abs(pixels - pixels[:, :1]).max(axis=2) > tolerance
    rows, columns = np.flatnonzero(content.any(axis=1)), np.flatnonzero(content.any(axis=0))
    if not rows.size:
        raise ValueError("The image shows nothing but its background")
    box = tuple(map(int, (columns[0], rows[0], columns[-1] + 1, rows[-1] + 1)))
    cropped = image.crop(box)
    return (cropped, box) if return_box else cropped


class BoardImage:
    """An image of the board divided into a grid of equal cells.

    Cells are addressed by their own grid coordinates, separate from the design's
    coordinates: x counts columns from the left and y rows from the top, both from
    0 up to max_x and max_y.
    """

    def __init__(self, image: Image.Image, pixel_size, max_x, max_y, name="", source_offset=(0, 0)):
        """pixel_size is one cell's (width, height) in image pixels; name is the board's, e.g. its component name."""
        width, height = pixel_size
        if max_x < 0 or max_y < 0:
            raise ValueError(f"A {image.width} x {image.height} image is smaller than one {width} x {height} cell")
        if (max_x + 1) * width > image.width or (max_y + 1) * height > image.height:
            raise ValueError(f"A {max_x + 1} x {max_y + 1} grid of {width} x {height} cells "
                             f"doesn't fit in a {image.width} x {image.height} image")
        self.image = image
        self._pixel_size = (width, height)
        self._max_x = max_x
        self._max_y = max_y
        self.name = name
        self.source_offset = tuple(source_offset)  # this image's top-left in the original export

    def get_pixel_size(self):
        return self._pixel_size

    def is_processed(self):
        """True for a BoardCell, already split out of its board; False for a whole board."""
        return False

    def cell_coords(self):
        """Grid coordinates (x, y) of every cell, row by row."""
        return [(x, y) for y in range(self._max_y + 1) for x in range(self._max_x + 1)]

    def cell_name(self, x, y):
        """The name a label file uses for cell (x, y), e.g. "Board_3_5"."""
        return f"{self.name}_{x}_{y}"
    
    def cell(self, x, y):
        """The cell at grid coordinates (x, y), cut out of the image, as a BoardCell named cell_name(x, y)."""
        if (x < 0 or x > self._max_x) or (y < 0 or y > self._max_y):
            raise ValueError(f"({x}, {y}) is outside the grid 0..{self._max_x} x 0..{self._max_y}")
        width, height = self._pixel_size
        left, top = x * width, y * height
        return BoardCell(self.cell_name(x, y), x, y, self.image.crop((left, top, left + width, top + height)),
                         source_offset=(self.source_offset[0]+left, self.source_offset[1]+top))

    def split_all(self):
        """Every cell of the board as a BoardCell, row by row (the order of cell_coords())."""
        return [self.cell(x, y) for x, y in self.cell_coords()]



class BoardCell(BoardImage):
    """One grid cell of a BoardImage: its label-file name, grid coordinates (x, y) on its board and pixels.

    A BoardImage of a single cell the size of the whole image; it can't be split further.
    """

    def __init__(self, name, x, y, image: Image.Image, source_offset=(0, 0)):
        super().__init__(image, image.size, 0, 0, name=name, source_offset=source_offset)
        self.x = x
        self.y = y

    def is_processed(self):
        return True

    def split_all(self):
        raise ValueError("You cannot split a board cell")



                
    
