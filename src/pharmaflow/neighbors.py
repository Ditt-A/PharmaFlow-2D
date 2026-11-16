"""Uniform cells plus a Verlet skin; candidate pairs sorted for reproducibility."""
import itertools
import numpy as np


def cell_pairs(x, radii, active, skin=0.0):
    size = 2 * float(np.max(radii)) + skin
    cells = {}
    for i in np.flatnonzero(active):
        key = tuple(np.floor(x[i] / size).astype(int))
        cells.setdefault(key, []).append(int(i))
    pairs = []
    for key, members in sorted(cells.items()):
        for i in members:
            for dx, dy in itertools.product((-1, 0, 1), repeat=2):
                for j in cells.get((key[0] + dx, key[1] + dy), ()):
                    if i < j and np.sum((x[i] - x[j])**2) < (radii[i] + radii[j] + skin)**2:
                        pairs.append((i, j))
    return np.asarray(sorted(pairs), dtype=np.int32).reshape(-1, 2)


class NeighborList:
    def __init__(self, skin):
        self.skin = skin
        self.reference = None
        self.active = None

    def get(self, x, radii, active):
        rebuild = self.reference is None or not np.array_equal(active, self.active)
        if not rebuild:
            rebuild = np.max(np.linalg.norm(x - self.reference, axis=1)) >= self.skin / 2
        if rebuild:
            self.pairs = cell_pairs(x, radii, active, self.skin)
            self.reference, self.active = x.copy(), active.copy()
        return self.pairs
