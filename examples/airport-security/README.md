# Airport security checkpoint

All apologies to airport security agents everywhere. This program simulates an
airport security checkpoint composed of 5 different lines. Travelers arrive
through both a Poisson process (departing travelers) and through a
batch-Poisson process (layovers). A common waiting queue welcomes all
travelers, where priority travelers pass in front of the commoners (yes, way
too real).

Once past this initial queue, an agent dispatches customers across five
luggage belts with body scanner, using a selection model.  This agent knows
there is space for 15 persons to wait at each belt. The first 10 travelers
waiting at each belt are hidden out of sight. Thus whenever the agent loses
sight of people waiting at one of the belts, he ushers up to 5 travelers from
the main queue over that belt. However, if he sees anybody (i.e. more than 10
travelers are waiting), he leaves this belt alone, and would rather have
people waiting in the main queue.

Each belt and scanner system is manned by a team of three agents, who take
coffee breaks at approximative 2-hour intervals (breaks lasting about 10
minutes), during which they do not process any traveler -- they finish
processing all in-processing travelers before going on their break. Agent
teams can process two travelers at a time. Once a traveler starts being
processed, they must prepare their luggage for scanning (which always takes
**so long**), then they go through scanning. Most travelers get the X-ray body
scan. Those who opt out of it (around 20% of them) get a lengthier patdown
instead.

At the end of their checkpoint processing, most travelers put back their belt
on and buckle back their luggage, then they leave the checkpoint. However, 5
travelers out of 1000 are instead sent for full luggage inspection, in a
facility of five agents. They finish their processing in there, after which
they leave the system.
