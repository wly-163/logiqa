"""开源门面：用户可见文案与 README 须保持仓配物流口径，且不写无法复现的评测数字。"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend" / "src"
README = ROOT / "README.md"

# 非仓配作业票据/组织称谓，避免与一线仓储用语混淆。
# 不扫「调度单号」「调度员」——仓储调度是物流本义。
OFF_DOMAIN = ("调度/检修", "检修规程", "工作票", "操作票", "两票", "调度室", "转检修")
SCAN_EXTRA = (
    ROOT / "tests" / "test_acl.py",
    ROOT / "tests" / "test_agent_runtime.py",
    ROOT / "kb_seed" / "seed_kb.py",
)


def _scan(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    return [f"{path.relative_to(ROOT)}: {token}" for token in OFF_DOMAIN if token in text]


def test_frontend_stays_on_logistics_copy():
    hits = []
    for path in FRONTEND.rglob("*"):
        if path.suffix not in {".vue", ".js"}:
            continue
        hits.extend(_scan(path))
    for path in SCAN_EXTRA:
        hits.extend(_scan(path))
    acl = (ROOT / "tests" / "test_acl.py").read_text(encoding="utf-8")
    assert "检修" not in acl and "调度" not in acl
    assert hits == [], "发现偏离仓配口径的文案：\n" + "\n".join(hits)


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
