"""Persist a scalar current-density grid and its physical metadata."""
import numpy as np

from .ScalarImage import load_scalar_image


def write_j_image(path, z, units, solution):
    x, y, j = load_scalar_image(path)
    valid = np.isfinite(j)
    if not valid.any() or np.any(j[valid] < 0):
        raise ValueError('Expected a nonnegative current-density magnitude with finite samples')
    j = np.where(valid, j, np.nan)
    npz = path.with_suffix('.npz')
    np.savez_compressed(npz, x=x, y=y, j=j, z=z, units=units,
                        field_units='A/m^2', quantity='|J|', solution=solution, valid=valid)
    iy, ix = np.unravel_index(np.nanargmax(j), j.shape)
    return {'quantity':'|J|', 'field units':'A/m^2', 'solution':solution,
            'image plane':f'z = {z} {units}, {len(x)} x {len(y)} pixels',
            'J min (A/m^2)':float(j[valid].min()), 'J max (A/m^2)':float(j[valid].max()),
            'peak at (x, y)':(float(x[ix]),float(y[iy])), 'missing pixels':int((~valid).sum()),
            'fld file':str(path), 'npz file':str(npz)}
