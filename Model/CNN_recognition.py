"""A small CNN for BoardImageDataset: can VCC/GND attach to this board cell?"""

import torch
from torch import nn


def conv_block(in_channels, out_channels):
    """3x3 convolution, batch norm and ReLU, then halve the size (ceil_mode keeps 1-pixel inputs at 1)."""
    return nn.Sequential(
        nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1, bias=False),
        nn.BatchNorm2d(out_channels),
        nn.ReLU(inplace=True),
        nn.MaxPool2d(2, ceil_mode=True),
    )


class CNN_recognition(nn.Module):
    """Images [B, 3, H, W] in 0..1 -> one logit per image, positive for "attachable".

    Works for any cell size (configs.GRID_SIZE): the features are averaged over the
    remaining area before the classifier. Train with
    nn.BCEWithLogitsLoss(pos_weight=dataset.pos_weight()).
    """

    def __init__(self, in_channels=3, channels=(16, 32, 64), dropout=0.3):
        super().__init__()
        sizes = (in_channels, *channels)
        self.features = nn.Sequential(*(conv_block(a, b) for a, b in zip(sizes, sizes[1:])))
        self.classifier = nn.Sequential(
            nn.AdaptiveAvgPool2d(1),
            nn.Flatten(),
            nn.Dropout(dropout),
            nn.Linear(channels[-1], 1),
        )

    def forward(self, images):
        """Logits [B]."""
        return self.classifier(self.features(images)).squeeze(1)

    @torch.no_grad()
    def predict(self, images, threshold=0.5):
        """True for the cells whose probability of being attachable is at least ``threshold``."""
        self.eval()
        return torch.sigmoid(self(images)) >= threshold
