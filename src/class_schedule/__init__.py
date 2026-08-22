"""Small, memorable API for editing and validating class schedules.

The legacy ``models``/``schedule`` stack (and everything only reachable
through it -- ``agent``, ``algorithm``, ``config``, ``checks``,
``conflicts``, ``solver``, ``changingsections``) has been archived under
``.dep/class_schedule_old/`` and is not re-exported here. This package
now exposes the ``class_model``/``schedule_model`` stack instead.
"""

from .class_model import (
    Class,
    CoreqClass,
    CrossListingClass,
    DeliveryMode,
    FourCreditClass,
    HybridClass,
    NormalClass,
    Section,
    SpecialClass,
)
from .schedule_model import Schedule

__all__ = [
    "Class",
    "CoreqClass",
    "CrossListingClass",
    "DeliveryMode",
    "FourCreditClass",
    "HybridClass",
    "NormalClass",
    "Schedule",
    "Section",
    "SpecialClass",
]
