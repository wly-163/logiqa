"""开源门面：用户可见文案与 README 不得残留电网口径或无法复现的评测数字。"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend" / "src"
README = ROOT / "README.md"

STALE = ("调度/检修", "检修规程")


def test_frontend_has_no_grid_dept_or_doc_type():
    hits = []
    for path in FRONTEND.rglob("*"):
        if path.suffix not in {".vue", ".js"}:
            continue
        text = path.read_text(encoding="utf-8")
        for token in STALE:
            if token in text:
                hits.append(f"{path.relative_to(ROOT)}: {token}")
    assert hits == [], "界面仍有电网时期部门/文档类型：\n" + "\n".join(hits)


def test_seed_prefixes_are_logistics():
    seed = (ROOT / "kb_seed" / "seed_kb.py").read_text(encoding="utf-8")
    assert "检修规程" not in seed


def test_readme_ci_badge_is_github_actions():
    text = README.read_text(encoding="utf-8")
    assert "github.com/wly-163/logiqa/actions/workflows/ci.yml/badge.svg" in text
    assert "img.shields.io/badge/CI-pytest-green.svg" not in text


def test_readme_does_not_claim_unreproducible_12_of_12():
    text = README.read_text(encoding="utf-8")
    assert "12/12" not in text
    assert "100%** (12" not in text


def test_readme_preview_images_exist():
    names = ("chat.png", "kg-3d.png", "twin.png")
    missing = [n for n in names if not (ROOT / "docs" / "images" / n).is_file()]
    assert missing == [], f"缺少 README 预览图: {missing}"
    text = README.read_text(encoding="utf-8")
    for n in names:
        assert f"docs/images/{n}" in text
