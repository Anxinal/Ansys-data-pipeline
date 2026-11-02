"""Project a fixed, pin-driven XY grid into a bottom-view image without resizing."""
from dataclasses import dataclass, replace
import math


@dataclass(frozen=True)
class PinGrid:
    model_box: tuple  # xmin, ymin, xmax, ymax in model units
    image_box: tuple  # pixel edges of that model box in the full exported image
    origin: tuple  # connector center for pin column=0, row=0
    pitch: tuple  # x increases with column; y decreases with row
    cell_size: tuple
    crop_offset: tuple = (0, 0)

    def __post_init__(self):
        if any(v <= 0 for v in (*self.pitch, *self.cell_size)):
            raise ValueError("Grid pitch and cell size must be positive")
        if self.model_box[2] <= self.model_box[0] or self.model_box[3] <= self.model_box[1]:
            raise ValueError("Model bounding box must have positive XY extents")
        if self.image_box[2] <= self.image_box[0] or self.image_box[3] <= self.image_box[1]:
            raise ValueError("Image bounding box must have positive pixel extents")

    @property
    def scale(self):
        return tuple((self.image_box[i+2]-self.image_box[i]) /
                     (self.model_box[i+2]-self.model_box[i]) for i in range(2))

    def center(self, column, row):
        return (self.origin[0] + column * self.pitch[0], self.origin[1] - row * self.pitch[1])

    def _world_to_full_pixel(self, x, y):
        # Bottom view: +X is screen-right, +Y is screen-down.
        return tuple(self.image_box[i] + (v-self.model_box[i]) * self.scale[i]
                     for i, v in enumerate((x, y)))

    def world_to_pixel(self, x, y):
        return tuple(v-self.crop_offset[i] for i,v in enumerate(self._world_to_full_pixel(x,y)))

    def cell_box(self, column, row):
        x, y = self.center(column, row)
        return (x-self.cell_size[0]/2, y-self.cell_size[1]/2,
                x+self.cell_size[0]/2, y+self.cell_size[1]/2)

    def pixel_box(self, column, row):
        box = self.cell_box(column, row)
        full = (*self._world_to_full_pixel(*box[:2]), *self._world_to_full_pixel(*box[2:]))
        # Round in the original image before translating. Rounding after cropping
        # can change half-pixel ties and shift boundaries by a pixel.
        return tuple(round(v)-self.crop_offset[i%2] for i,v in enumerate(full))

    def intersecting_indices(self):
        xmin, ymin, xmax, ymax = self.model_box
        x0, y0 = self.origin
        sx, sy = self.cell_size
        px, py = self.pitch
        columns = range(math.ceil((xmin-x0-sx/2)/px), math.floor((xmax-x0+sx/2)/px)+1)
        # Increasing screen row means decreasing pin row in a bottom view.
        rows = range(math.floor((y0-ymin+sy/2)/py), math.ceil((y0-ymax-sy/2)/py)-1, -1)
        return list(columns), list(rows)

    def after_crop(self, left, top):
        """Translate only pixel coordinates; the physical grid origin stays fixed."""
        return replace(self, crop_offset=(self.crop_offset[0]+left, self.crop_offset[1]+top))

    def index_at(self, x, y):
        return (round((x-self.origin[0])/self.pitch[0]), round((self.origin[1]-y)/self.pitch[1]))
