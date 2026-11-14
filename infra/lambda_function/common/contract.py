"""โหลด data contract: ใน Lambda ใช้แพ็กเกจ data_contract ที่ zip ไว้ข้างๆ, ตอนพัฒนาในรีโปใช้ script/data_contract"""
try:
    from data_contract import BLOCK, evaluate, get_ruleset  # noqa: F401  (แพ็กเกจที่ bundle ใน zip)
except ImportError:  # pragma: no cover
    from script.data_contract import BLOCK, evaluate, get_ruleset  # noqa: F401  (รันจาก root ของรีโป)
