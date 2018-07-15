# greensim: discrete event simulation toolkit

This is a set of simple tools for modeling and running simulations of discrete
event systems. It is composed of two classes: `Simulator`, which articulates a
dynamic series of events, and `Process`, the base class for a part of the
system that generates events.

The typical way to model a discrete event system using this framework is to
code its components by subclassing `Process`, and implementing the `_run`
method of the resulting class. This method schedules implements the behaviour
of a process of the system, indicating what happens at various moments within
this process, and using method `advance()` to forward the simulation to the
next moment.

One then creates an instance of `Simulator` and instantiates their processes
around it. A simulation is then launched by calling method `start()` of the
`Simulator` instance. The simulation stops, thereby returning from `start()`,
when the simulator runs out of events, or if one of the processes invokes
its method `stop()`. The simulation instance can be resumed by calling
`start()` over again, and so on.

Take a look at the files in [examples]() subdirectory to get a concrete
understanding.

Reference documentation for classes `Simulator` and `Process` is available as
docstrings.

