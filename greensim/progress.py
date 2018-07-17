"""
Progress tracking tools for simulations.
"""

from math import ceil, inf
import sys
import time
from typing import Callable, Sequence, Tuple, IO, Optional, Union

from greensim import now, advance, stop


MetricProgress = Sequence[float]
MeasureProgress = Callable[[], MetricProgress]
MeasureComparison = Sequence[Tuple[float, float]]
CaptureProgress = Callable[[float, float, MeasureComparison], None]


def combine(*measures: MeasureProgress) -> MetricProgress:
    """Combines multiple progress measures into one metric."""
    return sum((list(measure()) for measure in measures), [])


def sim_time():
    return [now()]


def capture_print(file_dest_maybe: Optional[IO] = None):
    """Progress capture that writes updated metrics to an interactive terminal."""
    file_dest: IO = file_dest_maybe or sys.stderr

    def _print_progress(progress_min: float, rt_remaining: float, _mc: MeasureComparison) -> None:
        nonlocal file_dest
        percent_progress = progress_min * 100.0
        time_remaining, unit = _display_time(rt_remaining)
        print(
            f"Progress: {percent_progress:.1f}% -- Time remaining: {time_remaining} {unit}          ",
            end="\r",
            file=file_dest
        )

    return _print_progress


def track_progress(
    measure: MeasureProgress,
    target: MetricProgress,
    interval_check: float,
    capture_maybe: Optional[CaptureProgress] = None
) -> None:
    """
    Tracks progress against a certain end condition of the simulation (for instance, a certain duration on the simulated
    clock), reporting this progress as the simulation chugs along. Stops the simulation once the target has been
    reached. By default, the progress is reported as printout on standard output, in a manner that works best for
    digital terminals.
    """

    def measure_to_target() -> MeasureComparison:
        return list(zip(measure(), target))

    def is_finished(progress: MeasureComparison) -> bool:
        return all(p >= t for p, t in progress)

    capture = capture_maybe or capture_print()
    rt_started = time.time()
    while True:
        advance(interval_check)

        rt_elapsed = time.time() - rt_started
        progress = measure_to_target()
        ratio_progress_min = min(m / t for m, t in progress)
        if ratio_progress_min == 0.0:
            rt_total_projected = inf
        else:
            rt_total_projected = rt_elapsed / ratio_progress_min
        capture(ratio_progress_min, rt_total_projected - rt_elapsed, progress)

        if is_finished(progress):
            stop()
            break


def _divide_round(dividend: Union[float, int], divider: Union[float, int]) -> int:
    return int(ceil(float(dividend) / divider))


def _display_time(seconds: float) -> Tuple[int, str]:
    if seconds == inf:
        delay = 1
        unit = "infinity"
    else:
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
