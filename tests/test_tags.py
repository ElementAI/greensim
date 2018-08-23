from greensim.tags import Tags, TaggedObject


class TestTag(Tags):
    # Prevent Pytest from complaining
    __test__ = False
    ALICE = 0
    BOB = "BOB"
    # By design, tags can point to any value
    CANADA: object = {}


def test_empty_init():
    tagged = TaggedObject()
    assert tagged._tag_set == set()


def test_tag_set_init():
    tagged = TaggedObject(TestTag.ALICE)
    assert tagged.has_tag(TestTag.ALICE)
    assert tagged._tag_set == set([TestTag.ALICE])


def test_tag_set_iterator():
    tags = set([TestTag.ALICE, TestTag.BOB, TestTag.CANADA])
    tagged = TaggedObject(*tags)
    collect = set()
    for tag in tagged.iter_tags():
        assert tag in tags
        collect |= set([tag])
    assert collect == tags


def test_tag_set_match():
    tagged = TaggedObject()
    tagged.tag_with(TestTag.ALICE)
    assert tagged.has_tag(TestTag.ALICE)
    assert not tagged.has_tag(TestTag.BOB)


def test_tag_apply():
    tagged = TaggedObject(TestTag.BOB)
    tagged.tag_with(TestTag.ALICE)
    assert tagged.has_tag(TestTag.ALICE)
    assert tagged._tag_set == set([TestTag.ALICE, TestTag.BOB])


def test_tag_set_apply():
    tagged = TaggedObject(TestTag.ALICE)
    tagged.tag_with(TestTag.ALICE, TestTag.BOB, TestTag.CANADA)
    assert tagged._tag_set == set([TestTag.ALICE, TestTag.BOB, TestTag.CANADA])


def test_tag_remove():
    tagged = TaggedObject(TestTag.ALICE, TestTag.BOB)
    tagged.untag(TestTag.ALICE)
    assert not tagged.has_tag(TestTag.ALICE)
    assert tagged._tag_set == set([TestTag.BOB])


def test_tag_set_remove():
    tagged = TaggedObject(TestTag.ALICE, TestTag.BOB, TestTag.CANADA)
    tagged.untag(TestTag.ALICE, TestTag.CANADA)
    assert tagged._tag_set == set([TestTag.BOB])


def test_tag_set_clear():
    tagged = TaggedObject(TestTag.ALICE, TestTag.BOB)
    tagged.clear_tags()
    assert tagged._tag_set == set()
