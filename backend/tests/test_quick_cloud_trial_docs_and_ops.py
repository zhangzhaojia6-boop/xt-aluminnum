from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding='utf-8-sig')


def test_gitignore_covers_quick_trial_artifacts() -> None:
    source = _read('.gitignore')

    assert '.tmp-pytest/' in source
    assert 'backend/.pytest-cache/' in source
    assert 'backend/.pytest-cache-2/' in source
    assert 'backend/pytest-cache-files-*/' in source
    assert 'frontend/tmp-review-home.png' in source
    assert 'frontend/frontend/' in source


def test_release_freeze_checklist_requires_clean_worktree_and_github_remote() -> None:
    source = _read('docs/发布冻结基线清单.md')

    assert '`git status --short` 不再包含测试缓存、临时截图和误生成目录' in source
    assert 'GitHub 远端已接入，云主机可直接拉代码' in source

