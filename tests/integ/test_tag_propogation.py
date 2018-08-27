from greensim import GREENSIM_TAG_ATTRIBUTE, now, Process, Simulator, tagged
from greensim.tags import Tags


# Greensim has an unusual allocation pattern that will cause this test to fail if the call to clear_tags()
# is removed from the Process __init__ method. The greenlet that calls tag_carrier will be recycled
# and will be used to call tag_receiver, and since it is not a new construction it will retain the
# tag that it initially took from tag_carrier


def test_tag_clear():
    sim._clear()

    @tagged(IntegTestTag.CANADA)
    def tag_carrier():
        pass

    sim.add(tag_carrier)
    sim.run()

    def tag_receiver():
        assert not Process.current().has_tag(IntegTestTag.CANADA)

    sim.add(tag_receiver)
    sim.run()


############################################################
# Define constants for the many tests of add(_in, _at) #
############################################################


class IntegTestTag(Tags):
    ALICE = 0
    BOB = ""
    CANADA = {}


flag = 0
sim = Simulator()


####################################################################################
# Helper functions to deal with simulations in the many tests of add(_in, _at) #
####################################################################################


# Wraps an arbitrary function in order to check that it is being called at the right time
# The returned function takes the tags of the argument function
def create_time_check(delay, fn):
    def time_check(*args, **kwargs):
        assert delay == now()
        fn(*args, **kwargs)

    # NB this is discouraged in Production code. Tags should be applied at the top level,
    # where they can be propogated down. This is just to keep the test helper generic
    if hasattr(fn, GREENSIM_TAG_ATTRIBUTE):
        time_check = tagged(*getattr(fn, GREENSIM_TAG_ATTRIBUTE))(time_check)

    return time_check


# Vanilla add, just passes arguments through and checks that fn is run using flag
def run_add(fn, *args, **kwargs):
    global flag
    flag = 0
    sim._clear()
    sim.add(fn, *args, **kwargs)
    sim.run()
    assert flag == 1


# Wraps fn in another function that checks the delay happened and passes arguments and tags through
def run_add_at(fn, *args, **kwargs):
    global flag
    flag = 0
    delay = 10

    sim._clear()
    sim.add_at(delay, create_time_check(delay, fn), *args, **kwargs)
    sim.run()
    assert flag == 1


# Same as above, but runs the simulation first to make sure the relative functionality of _in is used
def run_add_in(fn, *args, **kwargs):
    global flag
    flag = 0
    delay = 10

    sim._clear()
    sim.run(delay)
    sim.add_in(delay, create_time_check(2 * delay, fn), *args, **kwargs)
    sim.run()
    assert flag == 1


short_tag_set = set([IntegTestTag.ALICE, IntegTestTag.BOB])


@tagged(*short_tag_set)
def tag_checker(tag_set):
    global flag, short_tag_set
    flag = 1
    assert tag_set == Process.current()._tag_set


def test_add_tags():
    run_add(tag_checker, short_tag_set)


def test_add_at_tags():
    run_add_at(tag_checker, short_tag_set)


def test_add_in_tags():
    run_add_in(tag_checker, short_tag_set)


# As defined in the __init__ method of Process, a new Process should take tags from
# the function it is passed, as well as the currently running Process
# These test that add shows consistent behavior


def test_add_propogate():

    @tagged(IntegTestTag.CANADA)
    def tag_propogator(tag_set):
        sim.add(tag_checker, tag_set | set([IntegTestTag.CANADA]))

    run_add(tag_propogator, short_tag_set)


def test_add_at_propogate():

    @tagged(IntegTestTag.CANADA)
    def tag_propogator(tag_set):
        sim.add_at(now() + 10, create_time_check(now() + 10, tag_checker), tag_set | set([IntegTestTag.CANADA]))

    run_add_at(tag_propogator, short_tag_set)


def test_add_in_propogate():

    @tagged(IntegTestTag.CANADA)
    def tag_propogator(tag_set):
        sim.add_in(10, create_time_check(now() + 10, tag_checker), tag_set | set([IntegTestTag.CANADA]))

    run_add_in(tag_propogator, short_tag_set)
