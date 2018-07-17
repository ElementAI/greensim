# greensim: discrete event simulation toolkit

[![CircleCI](https://circleci.com/gh/ElementAI/greensim.svg?style=svg)](https://circleci.com/gh/ElementAI/greensim)

This is a set of simple tools for modeling and running simulations of discrete
event systems. It is based on the implementation of each independant part of
the system that generates events into a function: these are the simulation's
*processes*. They are then `add()`ed to a `Simulator` object, which
coordinates the timeline over which processes execute. Such functions indicate
what happens at various moments within this process, and using functions
`advance()` and `pause()` (valid only in context of process routines) to
forward the simulation to the next moment.

With processes duly added to the `Simulator` object, the simulation is
launched by calling its method `run()`. The simulation stops, thereby
returning from `run()`, when the simulator runs out of events, or if one of
the processes invokes function `stop()`. The simulation can be resumed by
calling method `run()` over again, and so on.

Take a look at the files in [examples]() subdirectory to get a concrete
understanding.

Reference documentation for classes `Simulator` and `Process` is available as
docstrings.
