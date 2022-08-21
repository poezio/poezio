from typing import Any, Dict, List, Tuple
from pathlib import Path

def to_curses_attr(fg: int, bg: int, attrs: str) -> int: ...
def run_cmdline_args(argv: List[str]) -> Tuple[Dict[Any, Any], bool]: ...

class XDG:
    cache_dir: Path
    config_dir: Path
    data_dir: Path
