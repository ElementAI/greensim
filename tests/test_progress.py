import time

import pytest

from greensim import Simulator, Process
from greensim.progress import _display_time, _divide_round, ProgressTracker, sim_time, combine


def test_divide_round():
    assert _divide_round(60, 10) == 6
    assert _divide_round(59, 10) == 6


def test_display_seconds():
    assert _display_time(0.8) == (1, "second")
    assert _display_time(1.0) == (1, "second")
    assert _display_time(90.0) == (90, "seconds")


def test_display_minutes():
    assert _display_time(90.1) == (2, "minutes")
    assert _display_time(120.1) == (3, "minutes")
    assert _display_time(90.0 * 60.0) == (90, "minutes")


def test_display_hours():
    assert _display_time(90.0 * 60.0 + 0.1) == (2, "hours")
    assert _display_time(36.0 * 60.0 * 60.0) == (36, "hours")


def test_display_days():
    assert _display_time(36.0 * 60.0 * 60.0 + 0.1) == (2, "days")
    assert _display_time(78 * 60.0 * 60.0) == (4, "days")


def test_combine():

    def _measure1():
        return [5.6, 8.9]

    def _measure2():
        return [9.3]

    def _measure3():
        return [2.3, 9.2, 8.9]

    assert combine(_measure1) == [5.6, 8.9]
    assert combine(_measure1, _measure2, _measure3) == [5.6, 8.9, 9.3, 2.3, 9.2, 8.9]


def has_tracker(sim, tracker):
    return any(event == tracker._gr.switch for _, event in sim.events())


def test_tracker_lifecycle():
    def capture_pass(progress, rt_remaining, mc):
        pass

    sim = Simulator()
    tracker = ProgressTracker(sim, sim_time(sim), [1000.0], 100.0, capture_pass)
    assert has_tracker(sim, tracker)

    def check_tracker(simm):
        nonlocal tracker
        assert has_tracker(simm, tracker)

    sim.schedule(150.0, check_tracker)
    sim.schedule(10000.0, lambda: sim.stop())
    sim.start()
    assert not has_tracker(sim, tracker)
    assert sim.now() == pytest.approx(1000.0)


def test_progress_capture():
    log = []

    def capture(progress_min, _rt_remaining, mc):
        nonlocal log
        log.append(progress_min)

    a = 0
    b = 0

    def set_ab(new_a, new_b):
        nonlocal a, b

        def _event(sim):
            nonlocal a, b
            a = new_a
            b = new_b

        return _event

    def measure():
        nonlocal a, b
        return (a, b)

    sim = Simulator()
    ProgressTracker(sim, measure, [10, 10], 10.0, capture)
    sim.schedule(15.0, set_ab(2, 0))
    sim.schedule(25.0, set_ab(4, 1))
    sim.schedule(35.0, set_ab(4, 6))
    sim.schedule(45.0, set_ab(5, 9))
    sim.schedule(55.0, set_ab(10, 10))
    sim.schedule(100.0, lambda sim: sim.stop())
    sim.start()

    assert sim.now() == pytest.approx(60.0)
    assert log == pytest.approx([0.0, 0.0, 0.1, 0.4, 0.5, 1.0])


class Sleeper(Process):

    def __init__(self, sim, interval, rt_delay):
        super().__init__(sim)
        self._interval = interval
        self._rt_delay = rt_delay

    def _run(self):
        while True:
            time.sleep(self._rt_delay)
            self.advance(self._interval)


def test_progress_real_time():
    log = []

    def capture(_progress_min, rt_remaining, mc):
        nonlocal log
        log.append(rt_remaining)

    sim = Simulator()
    ProgressTracker(sim, sim_time(sim), [100.0], 20.0, capture)
    Sleeper(sim, 10.0, 0.1)
    sim.start()

    assert log == pytest.approx([0.8, 0.6, 0.4, 0.2, 0.0], abs=1e-2)
