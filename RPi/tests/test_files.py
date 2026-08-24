"""④ 파일관리 — LIST_FILES / RENAME / MEMO (앱 파일탭)."""
import pytest

from pi.comm.files import FileManager, FileError


@pytest.fixture
def fm(tmp_path):
    (tmp_path / "run_b.csv").write_text("x")
    (tmp_path / "run_a.csv").write_text("x")
    (tmp_path / "notes.txt").write_text("x")
    return FileManager(tmp_path)


def test_list_returns_sorted_csv_only(fm):
    assert fm.list() == ["run_a.csv", "run_b.csv"]


def test_list_on_missing_dir_is_empty(tmp_path):
    assert FileManager(tmp_path / "nope").list() == []


def test_rename_moves_file(fm, tmp_path):
    fm.rename("run_a.csv", "run_a_비포장_건조.csv")
    assert fm.list() == ["run_a_비포장_건조.csv", "run_b.csv"]


def test_rename_missing_source_raises(fm):
    with pytest.raises(FileError):
        fm.rename("ghost.csv", "x.csv")


def test_rename_existing_target_raises(fm):
    with pytest.raises(FileError):
        fm.rename("run_a.csv", "run_b.csv")


@pytest.mark.parametrize("bad", ["../x.csv", "sub/x.csv", "x.txt", "", "..\\x.csv"])
def test_rename_rejects_unsafe_or_non_csv_names(fm, bad):
    with pytest.raises(FileError):
        fm.rename("run_a.csv", bad)


def test_memo_writes_sidecar_and_rename_carries_it(fm, tmp_path):
    fm.memo("run_a.csv", "비 온 뒤")
    assert (tmp_path / "run_a.memo.txt").read_text(encoding="utf-8") == "비 온 뒤"
    fm.rename("run_a.csv", "run_a_비포장_젖음.csv")
    assert (tmp_path / "run_a_비포장_젖음.memo.txt").read_text(encoding="utf-8") == "비 온 뒤"
    assert not (tmp_path / "run_a.memo.txt").exists()


def test_memo_missing_file_raises(fm):
    with pytest.raises(FileError):
        fm.memo("ghost.csv", "x")
