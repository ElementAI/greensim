from functools import reduce
from itertools import takewhile, repeat
from random import Random

import pytest

from greensim import Simulator, now, stop
from greensim.random import constant, linear, bounded, project_int, uniform, expo, normal, poisson_process, \
    set_default_random, _get_default_random, distribution


@pytest.fixture
def rng():
    return Random(123456789)


def test_default_random(rng):
    set_default_random(rng)
    assert _get_default_random() is rng


def check_vr(vr, expected, num=5):
    approx = pytest.approx
    if isinstance(expected[0], int):
        def ident(n):
            return n
        approx = ident
    #New in pytest 3.7
    if len(expected) > 0 and isinstance(expected[0], float):
        expected = approx(expected)
    assert expected == [v for _, v in takewhile(lambda p: p[0] < num, enumerate(vr))]


def test_constant():
    check_vr(constant(4), [4, 4, 4, 4, 4])


def test_linear():
    check_vr(linear(constant(5), 8, 2), list(repeat(42, 5)))


def test_bounded():
    vr = [1, 10, 100, 5, 8]
    for lower, upper, expected in [
        (None, None, [1, 10, 100, 5, 8]),
        (5, None, [5, 10, 100, 5, 8]),
        (None, 8, [1, 8, 8, 5, 8]),
        (8, 10, [8, 10, 10, 8, 8])
    ]:
        check_vr(bounded(vr, lower, upper), expected)


def test_project_int():
    check_vr(project_int([8.9, 4.1, -1.2, -0.89, 8.0]), [8, 4, -1, 0, 8])


def test_uniform(rng):
    check_vr(
        uniform(-10.0, 10.0, rng),
        [2.828012323717452, 0.8437853619389895, 9.863501325665442, 6.865042733738331, 6.234678566758809] +
        [-2.056525798439992, 8.741902158240851, 3.782053063316324, -2.057790229480325, -2.979496151539105],
        num=10
    )


def test_expo(rng):
    for mean, expected in [
        (0.1, [0.10255494361223205, 0.07812994293988781, 0.4987172649793017, 0.18531167307385135, 0.1669899041911445]),
        (10.0, [27.661313426569077, 11.682924957776319, 5.060213304302473, 4.323613803242847, 5.101643952899731])
    ]:
        check_vr(expo(mean, rng), expected)


def test_normal(rng):
    check_vr(
        normal(1.0, 10.0, rng),
        [6.2986237946521895, 9.871348510026426, -1.7198253631192353, -2.790200214990211, -11.540548443098107]
    )


def test_poisson_process(rng):
    log = [0.0]
    num = 0

    @poisson_process(10.0, rng)
    def proc():
        nonlocal num
        log.append(now())
        num += 1
        if num >= 5:
            stop()

    sim = Simulator()
    sim.add(proc)
    sim.run()
    assert pytest.approx(
        reduce(
            lambda cs, x: cs + [cs[-1] + x],
            [0.10255494361223205, 0.07812994293988781, 0.4987172649793017, 0.18531167307385135, 0.1669899041911445],
            [0.0]
        )) == log


def test_distribution_dict(rng):
    check_vr(
        distribution({"asdf": 5, "qwer": 4, "zxcv": 1}, rng),
        ["qwer", "qwer", "zxcv", "qwer", "qwer", "asdf", "zxcv", "qwer", "asdf", "asdf"],
        num=10
    )


def test_distribution_list(rng):
    check_vr(
        distribution(["asdf", "qwer", "zxcv"], rng),
        ["qwer", "qwer", "zxcv", "zxcv", "zxcv", "qwer", "zxcv", "zxcv", "qwer", "qwer"],
        num=10
    )
