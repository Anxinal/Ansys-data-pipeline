import random
from itertools import combinations

from configs import SAMPLER_SEED
from .PositionPair import TerminalPositionPair

class PositionSampler:
    _instance = None

    def __new__(cls):
        # cls's own attribute: a subclass must not be handed its parent's instance.
        if cls.__dict__.get("_instance") is None:
            cls._instance = super().__new__(cls)
            cls._instance._rng = random.Random(SAMPLER_SEED)
        return cls._instance

    @classmethod
    def reset(cls):
        cls._instance = None

    def sample_pair(self, positions: list):
        """Sample two different feasible positions as a TerminalPositionPair (VCC, GND)."""
        if len(positions) < 2:
            raise ValueError(f"Need at least 2 feasible positions to sample a pair, got {len(positions)}")
        vcc, gnd = self._rng.sample(positions, 2)
        return TerminalPositionPair(vcc, gnd)

    def sample_pair_batch(self, positions, n: int):
        """Sample ``n`` GND/VCC pairs independently."""
        if n <= 0:
            raise ValueError("Batch size needs to be at least 1")
        return [self.sample_pair(positions) for _ in range(n)]

class AllCombinationSampler(PositionSampler):
    """Every pair of two different positions, each once: (p0, p1), (p0, p2), ..., (p1, p2), ..."""

    def sample_pair_batch(self, positions, n=-1):

        pairs = list(combinations(positions, 2))
        n = len(pairs) if n == -1 else n
        if not 1 <= n <= len(pairs):
            raise ValueError(f"Batch size must be 1..{len(pairs)} for {len(positions)}")
        return [TerminalPositionPair(vcc, gnd) for vcc, gnd in pairs[:n]]

