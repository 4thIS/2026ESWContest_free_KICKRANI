"""④ 파일관리 — 앱 파일탭(LIST_FILES / RENAME / MEMO). 공통계약 계약 2.

수집 CSV 폴더(config.LOG_DIR) 안에서만 동작. 파일명은 경로 구분자·상위경로 금지,
`.csv`만 허용(디렉터리 탈출 방지). 메모는 `<이름>.memo.txt` 사이드카에 저장하며
RENAME 시 함께 옮긴다. 실패는 FileError(message) → 서버가 ERROR 응답.
"""
from pathlib import Path

from pi.config import LOG_DIR

_MEMO_SUFFIX = ".memo.txt"


class FileError(Exception):
    pass


class FileManager:
    def __init__(self, out_dir=LOG_DIR):
        self._dir = Path(out_dir)

    def list(self):
        if not self._dir.is_dir():
            return []
        return sorted(p.name for p in self._dir.iterdir() if p.is_file() and p.suffix == ".csv")

    def rename(self, old: str, new: str) -> None:
        src, dst = self._path(old), self._path(new)
        if not src.is_file():
            raise FileError(f"파일 없음: {old}")
        if dst.exists():
            raise FileError(f"이미 존재: {new}")
        src.rename(dst)
        memo = self._memo_path(src)
        if memo.exists():
            memo.rename(self._memo_path(dst))

    def memo(self, file: str, memo: str) -> None:
        p = self._path(file)
        if not p.is_file():
            raise FileError(f"파일 없음: {file}")
        self._memo_path(p).write_text(memo, encoding="utf-8")

    # ── 내부 ──
    def _path(self, name: str) -> Path:
        if not name or "/" in name or "\\" in name or name in (".", "..") \
                or not name.endswith(".csv") or Path(name).name != name:
            raise FileError(f"잘못된 파일명: {name!r}")
        return self._dir / name

    @staticmethod
    def _memo_path(csv_path: Path) -> Path:
        return csv_path.with_name(csv_path.name[:-4] + _MEMO_SUFFIX)
