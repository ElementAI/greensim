from enum import Enum
from typing import Iterator, Set


# This class should remain empty so that it can be subclassed by users
class Tags(Enum):
    """
    Empty superclass for Enums containing custom tags for Greensim TaggedObject's
    """
    pass


class TaggedObject:
    """
    Provides standardized methods for managing tags on generic objects

    Tags can be created by extending the Tags class, which is an Enum

    Methods on this class are all wrappers around standard Python set() methods
    """

    # Use a set since tags are order-independant and should be unique
    _tag_set: Set[Tags] = set()

    def __init__(self, *tag_set: Tags) -> None:
        self._tag_set = set(tag_set)

    def iter_tags(self) -> Iterator[Tags]:
        return iter(self._tag_set)

    def has_tag(self, needle: Tags) -> bool:
        """
        Applies the "in" operator to search for the argument in the set of tags
        """
        return needle in self._tag_set

    def tag_with(self, *new_tags: Tags) -> None:
        """
        Take the union of the current tags and the tags in the argument,
        make the union the new set of tags for this object
        """
        self._tag_set |= set(new_tags)

    def untag(self, *drop_tags: Tags) -> None:
        """
        Take the difference of the current tags and the tags in the argument,
        make the difference the new set of tags for this object
        """
        self._tag_set -= set(drop_tags)

    def clear_tags(self) -> None:
        """
        Remove all tags
        """
        self._tag_set.clear()
