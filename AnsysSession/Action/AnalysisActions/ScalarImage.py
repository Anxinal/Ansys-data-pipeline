"""Read scalar AEDT grid exports independently of the field quantity."""
import numpy as np


def load_scalar_image(path):
    rows = []
    with open(path, encoding='utf-8', errors='replace') as stream:
        for line in stream:
            parts = line.replace(',', ' ').replace('D', 'E').split()
            if len(parts) != 4:
                continue
            try:
                rows.append([float(part) for part in parts])
            except ValueError:
                continue
    if not rows:
        raise ValueError(f'No x, y, z, value rows in {path}')
    data = np.array(rows)
    xc, yc = np.round(data[:,0],9), np.round(data[:,1],9)
    x, y = np.unique(xc), np.unique(yc)
    values = np.full((len(y),len(x)), np.nan)
    values[np.searchsorted(y,yc), np.searchsorted(x,xc)] = data[:,3]
    return x,y,values
