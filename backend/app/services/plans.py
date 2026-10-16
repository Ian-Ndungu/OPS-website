"""The ONLY two Mythic Circle plans. These are code constants, not database
rows or CMS settings, so no admin screen can change them."""
from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True)
class Plan:
    code: str
    members: int
    monthly_kes: int
    months: int

    @property
    def per_member_total(self) -> int:
        return self.monthly_kes * self.months

    @property
    def cohort_target(self) -> int:
        return self.per_member_total * self.members

    @property
    def payout_per_member(self) -> int:
        return self.per_member_total


PLANS = MappingProxyType({
    "A": Plan("A", 7, 1000, 7),
    "B": Plan("B", 10, 700, 10),
})
MEMBER_CAP_KES = 7000

for _p in PLANS.values():
    assert _p.per_member_total == MEMBER_CAP_KES


def plan_for_size(size: int) -> Plan:
    for p in PLANS.values():
        if p.members == size:
            return p
    raise ValueError("Cohort size must be 7 or 10")


def plan_by_code(code: str) -> Plan:
    try:
        return PLANS[code]
    except KeyError:
        raise ValueError("Unknown plan")
