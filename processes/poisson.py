import random
from typing import List

from sim import Process, Simulator


class PoissonProcess(Process):

    def __init__(self, simulator: Simulator, lambda_: float, max_samples: int = None) -> None:
        super().__init__(simulator)
        self.lambda_ = lambda_
        self.max_samples = max_samples

        self.rand = random.Random()
        self.times: List[float] = []
        self.delays: List[float] = []
        self.count = 0

    def run(self):
        while True:
            if self.max_samples and self.count >= self.max_samples:
                # print(f"Reached max_samples of {self.max_samples}.")
                return

            self.times.append(self.sim.now())

            delay = self.rand.expovariate(1 / self.lambda_)
            self.delays.append(delay)

            self.advance(delay)

            self.count += 1
