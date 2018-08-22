from greensim.tags import GreensimTag, TaggedObject


class TestTag(GreensimTag):
    # Prevent Pytest from complaining
    __test__ = False
    ALICE = 0
    BOB = "BOB"
    # By design, tags can point to any value
    CANADA: object = {}


def test_empty_init():
    tagged = TaggedObject()
    assert tagged.tag_set == set()


def test_tag_set_init():
    ts = set([TestTag.ALICE])
    tagged = TaggedObject(ts)
    assert tagged.match(TestTag.ALICE)
    assert tagged.tag_set == ts


def test_tag_set_match():
    tagged = TaggedObject(set())
    tagged.apply(TestTag.ALICE)
    assert tagged.match(TestTag.ALICE)
    assert not tagged.match(TestTag.BOB)


def test_tag_apply():
    tagged = TaggedObject(set([TestTag.BOB]))
    tagged.apply(TestTag.ALICE)
    assert tagged.match(TestTag.ALICE)
    assert tagged.tag_set == set([TestTag.ALICE, TestTag.BOB])


def test_tag_set_apply():
    tagged = TaggedObject(set([TestTag.ALICE]))
    tagged.apply_set([TestTag.ALICE, TestTag.BOB, TestTag.CANADA])
    assert tagged.tag_set == set([TestTag.ALICE, TestTag.BOB, TestTag.CANADA])


def test_tag_remove():
    tagged = TaggedObject(set([TestTag.ALICE, TestTag.BOB]))
    tagged.remove(TestTag.ALICE)
    assert not tagged.match(TestTag.ALICE)
    assert tagged.tag_set == set([TestTag.BOB])


def test_tag_set_remove():
    tagged = TaggedObject(set([TestTag.ALICE, TestTag.BOB, TestTag.CANADA]))
    tagged.remove_set([TestTag.ALICE, TestTag.CANADA])
    assert tagged.tag_set == set([TestTag.BOB])


def test_tag_set_clear():
    tagged = TaggedObject(set([TestTag.ALICE, TestTag.BOB]))
    tagged.clear()
    assert tagged.tag_set == set()
