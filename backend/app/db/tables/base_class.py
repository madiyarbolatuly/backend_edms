from enum import Enum as PyEnum

class DocStatus(str, PyEnum):
    """
    Enum for status of document
    """

    public = "public"
    private = "private"
    shared = "shared"
    deleted = "deleted"
    archived = "archived"
    draft     = "draft"
    review    = "review"
    published = "published"
    


class NotifyEnum(str, PyEnum):
    """
    Enum for status of notification
    """

    read = "read"
    unread = "unread"

    @classmethod
    def has_value(cls, value):
        return value in cls._value2member_map_
