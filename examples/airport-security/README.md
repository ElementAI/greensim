# Airport security checkpoint

All apologies to airport security agents everywhere. This program simulates an
airport security checkpoint composed of 5 different lines. Travelers arrive
through both a Poisson process (departing travelers -- about 6 per hour) and
through a batch-Poisson process (layovers). For the latter travelers, a plane
lands about every 45 minutes, and between about 20 and 50 of its passengers
must pass through the security checkpoint.  A common waiting queue welcomes
all travelers, where priority travelers (about 1% of all travelers) pass in
front of the commoners (yes, way too real).

Once past this initial queue, an agent dispatches customers across four
luggage belts with body scanners, using a selection algorithm. This agent knows
there is space for about 10 persons at each belt. The first 5 travelers
present at each belt are out of sight. Thus whenever the agent loses sight of
people waiting at one of the belts, they usher up to 5 travelers from the main
queue over that belt. However, if they see anybody (i.e. more than 5
travelers are standing at the belt), he leaves this belt alone, and keep
people waiting in the main queue. Also, dispatching the main queue is tedious
work, so agents rotate on this job often, to the extent where there is always
dispatching service.

Once a traveler hops over to his assigned belt, they must prepare their
luggage and wearables for scanning (which takes at least 5 seconds, but on
average 30, and often more). Each belt and scanner system is manned by a team
of three agents, who take coffee breaks at approximative 2-hour intervals
(breaks lasting about 10 minutes), during which they do not process any
traveler. First the belt operator gets up and leaves; the agents finish
scanning or patting down their current traveler before following off. Luggage
belts and scanner lines do not acknowledge traveler priority, and process them
first in, first out.  Agent teams can process two travelers at a time.  Most
travelers get the X-ray body scan, which takes exactly 8~seconds. Those who
opt out of it (around 20% of them) get a lengthier patdown instead, which
lasts between 20 and 40 seconds, more or less.  At the end of their checkpoint
processing, most travelers put back their belt on and buckle back their
luggage (again, at least 5 seconds, on average 30, often more), then they
leave the checkpoint. Duty-free shops await!

Over a period of 10 days, we will measure the average time it takes for
travelers to cross the whole checkpoint. In addition, so as to evaluate the
economical efficiency of having this many luggage / body scanners, we will
mesure which part of the simulation time these stations are running empty,
i.e. having no traveler standing in them, either waiting or being processed.
