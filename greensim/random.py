from random import Random
from itertools import repeat
from numbers import Real
from typing import Any, Callable, TypeVar, Optional, Iterator, cast, Iterable, List, Mapping, Union

from greensim import happens


T = TypeVar("T")
VarRandom = Iterator[T]
RandomOpt = Optional[Random]


_default_random: Random = Random()


def set_default_random(rng: Random) -> None:
    global _default_random
    _default_random = rng


def _get_default_random() -> Random:
    """For testing purposes only."""
    return _default_random


def _ordef(rng: RandomOpt) -> Random:
    return rng or _default_random


def constant(value: T) -> VarRandom[T]:
    yield from repeat(value)


def _vr_from_fn(fn: Callable[..., T], *args: Any, **kwargs: Any) -> VarRandom[T]:
    while True:
        yield fn(*args, **kwargs)


def linear(vr: VarRandom[Real], slope: Real, shift: Real) -> VarRandom[Real]:
    yield from map(lambda x: slope * x + shift, vr)


def bounded(gen: VarRandom[Real], lower: Optional[Real] = None, upper: Optional[Real] = None) -> VarRandom[Real]:
    for x in gen:
        if lower is not None:
            x = max(lower, x)
        if upper is not None:
            x = min(x, upper)
        yield x


def project_int(vr: VarRandom[Real]) -> VarRandom[int]:
    yield from map(cast(Callable[[Real], int], int), vr)


def uniform(lower: Real, upper: Real, rng: RandomOpt = None) -> VarRandom[float]:
    yield from _vr_from_fn(_ordef(rng).uniform, lower, upper)


def expo(mean: Real, rng: RandomOpt = None) -> VarRandom[float]:
    yield from _vr_from_fn(_ordef(rng).expovariate, 1.0 / mean)


def normal(mean: Real, std_dev: Real, rng: RandomOpt = None) -> VarRandom[float]:
    yield from _vr_from_fn(_ordef(rng).normalvariate, mean, std_dev)


def poisson_process(mean_rate: Real, rng: RandomOpt = None) -> Callable[..., Any]:
    return happens(expo(1.0 / mean_rate, rng))


def distribution(distr: Union[List[T], Mapping[T, Real]], rng: RandomOpt = None) -> VarRandom[T]:
    if isinstance(distr, Mapping):
        vw = list(distr.items())
        values = [v for v, _ in vw]
        weights = [w for _, w in vw]
    else:
        values = distr
        weights = [1 for v in values]
    yield from map(lambda x: x[0], _vr_from_fn(_ordef(rng).choices, values, weights=weights))
