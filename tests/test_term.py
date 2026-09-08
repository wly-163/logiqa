"""术语归一化单测。"""
from app.services.term_service import normalize


def test_alias_normalized():
    assert "自动导引车" in normalize("AGV是核心设备")


def test_standard_not_harmed():
    # 最后一公里送装一体 不应被误伤成重复后缀
    n = normalize("最后一公里送装一体运行")
    assert "最后一公里送装一体一体" not in n
    assert "最后一公里送装一体运行" in n


def test_multi_terms():
    n = normalize("VMI 与 AGV 配合")
    assert "供应商管理库存" in n
    assert "自动导引车" in n
