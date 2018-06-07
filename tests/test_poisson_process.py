from processes.poisson import PoissonProcess
from sim import Simulator

import statistics
import math


def test_poisson_process():
    sim = Simulator()
    nb_samples = 10000
    p = PoissonProcess(sim, lambda_=5, max_samples=nb_samples)
    sim.start()

    assert len(p.times) == nb_samples
    assert len(p.delays) == nb_samples

    assert math.isclose(statistics.mean(p.delays), 5, rel_tol=0.1)
