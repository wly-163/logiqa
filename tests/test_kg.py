from app.services.kg_service import _parse_triples


def test_parse_triples_json():
    ans = '[{"s":"自动导引车","r":"发生","o":"温度过高"}]'
    out = _parse_triples(ans)
    assert len(out) == 1
    assert out[0] == {"s": "自动导引车", "r": "发生", "o": "温度过高"}


def test_parse_triples_fenced():
    ans = '```json\n[{"s":"叉车","r":"拒动","o":"故障"}]\n```'
    out = _parse_triples(ans)
    assert len(out) == 1
    assert out[0]["s"] == "叉车"
