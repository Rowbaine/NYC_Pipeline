"""Data contract rules สำหรับ ValidateFunction / TransformFunction

ตัวอย่างการใช้งาน
    from script.data_contract import get_ruleset, evaluate
    rs = get_ruleset("green")
    counts, block_mask = evaluate(table, rs.RULES)
"""
from . import fhv, fhvhv, green, yellow
from .base import BLOCK, INFO, WARN, Rule, evaluate, violation_mask

RULESETS = {"yellow": yellow, "green": green, "fhv": fhv, "fhvhv": fhvhv}


def get_ruleset(taxi_type: str):
    try:
        return RULESETS[taxi_type]
    except KeyError:
        raise ValueError(f"ไม่รู้จักประเภท: {taxi_type} (ต้องเป็น {sorted(RULESETS)})") from None
