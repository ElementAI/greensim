"""
Progress tracking tools for simulations.
"""

from math import ceil, inf
import sys
import time
from typing import cast, Callable, Sequence, Tuple, IO, Optional

from sim import Simulator, Process


MetricProgress = Sequence[float]
MeasurerProgress = Callable[[], MetricProgress]  # Typically set up as a closure or a bound method.
MeasureComparison = Sequence[Tuple[float, float]]
CapturerProgress = Callable[[float, float, MeasureComparison], None]


def combine(*measurers: Sequence[MeasurerProgress]) -> MetricProgress:
    """Combines multiple progress measures into one metric."""
    return sum((list(measurer()) for measurer in measurers), [])


def sim_time(sim: Simulator):
    """Progress measure based on the simulated clock."""
    return lambda: [sim.now()]


def capturer_print(file_dest_maybe: Optional[IO] = None):
    file_dest: IO = file_dest_maybe or sys.stderr
    def _print_progress(progress_min: float, rt_remaining: float, _mc: MeasureComparison) -> None:
        percent_progress = progress_min * 100.0
        time_remaining, unit = _display_time(rt_remaining)
        print(
            f"Progress: {percent_progress:.1f}% -- Time remaining: {time_remaining} {unit}          ",
            end="\r",
            file=self._output
        )


class ProgressTracker(Process):
    """
    Tracks progress against a certain end condition of the simulation (by
    default, it is a certain duration on the simulated clock), reporting this
    progress as the simulation chugs along. Stops the simulation once the
    target has been reached.
    """

    def __init__(
        self,
        sim: Simulator,
        measurer: MeasurerProgress,
        target: MetricProgress,
        interval_check: float,
        capturer: Optional[CapturerProgress] = None
    ):
        super().__init__(sim)
        self._measurer = measurer
        self._target = target
        self._interval_check = interval_check
        self._capturer = capturer or capturer_print(sys.stderr)
        self._rt_started: Optional[float] = None

    def _measure(self) -> MeasureComparison:
        return list(zip(self._measurer(), self._target))

    def is_finished(self) -> bool:
        """
        Determines whether simulation is finished, according to given
        progress measure and target.
        """
        return all(p >= t for p, t in self._measure())

    def _run(self) -> None:
        while True:
            if self._rt_started is None:
                self._rt_started = time.time()
            else:
                t = time.time()
                rt_elapsed = t - cast(float, self._rt_started)
                measure = self._measure()
                ratio_progress_min = min(p / t for p, t in measure)
                if ratio_progress_min == 0.0:
                    rt_total_projected = inf
                else:
                    rt_total_projected = rt_elapsed / ratio_progress_min
                self._capturer(ratio_progress_min, rt_total_projected - rt_elapsed, measure)

                if self.is_finished():
                    self.sim.stop()
                    return

            self.advance(self._interval_check)


def _divide_round(dividend: int, divider: int) -> int:
    return int(ceil(float(dividend) / divider))


def _display_time(seconds: float) -> Tuple[int, str]:
    delay = _divide_round(seconds, 1)
    unit = "second"

    if delay > 90:
        delay = _divide_round(delay, 60)
        unit = "minute"

        if delay > 90:
            delay = _divide_round(delay, 60)
            unit = "hour"

            if delay > 36:
                delay = _divide_round(delay, 24)
                unit = "day"

    if delay > 1:
        unit += "s"

    return delay, unit
