from enum import Enum, unique
from typing import Iterable, Set


@unique
class GreensimTag(Enum):
    """
    Empty superclass for Enums containing custom tags for Greensim TaggedObject's
    The @unique decorator is applied so labels are all distinct
    """
    pass


class TaggedObject(object):
    """
    Provides standardized methods for managing tags on generic objects

    Tags can be created by extending the GreensimTag class, which is an Enum

    Methods on this class are all wrappers around standard Python set() methods
    """

    # Use a set since tags are order-independant and should be unique
    _tag_set: Set[GreensimTag] = set()

    def __init__(self, tag_set: Iterable[GreensimTag] = []) -> None:
        self._tag_set = set(tag_set)

    @property
    def tag_set(self) -> Set[GreensimTag]:
        return self._tag_set

    def match(self, needle: GreensimTag) -> bool:
        """
        Applies the "in" operator to search for the argument in the set of tags
        """
        return needle in self._tag_set

    def apply(self, new_tag: GreensimTag) -> None:
        """
        Convenience method to apply one tag with apply_set
        """
        self.apply_set([new_tag])

    def apply_set(self, new_tags: Iterable[GreensimTag]) -> None:
        """
        Take the union of the current tags and the tags in the argument,
        make the union the new set of tags for this object
        """
        self._tag_set = self._tag_set.union(set(new_tags))

    def remove(self, drop_tag: GreensimTag) -> None:
        """
        Convenience method to remove one tag with remove_set
        """
        self.remove_set([drop_tag])

    def remove_set(self, drop_tags: Iterable[GreensimTag]) -> None:
        """
        Take the difference of the current tags and the tags in the argument,
        make the difference the new set of tags for this object
        """
        self._tag_set = self._tag_set.difference(set(drop_tags))

    def clear(self) -> None:
        """
        Remove all tags
        """
        self._tag_set.clear()
