"""Replace artifacts only after their complete content is written."""
import os
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path

_replace_lock = threading.Lock()


@contextmanager
def atomic_output_path(path: Path):
    """Publish an artifact only after its writer completes successfully."""
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    os.close(descriptor)
    temporary = Path(name)
    try:
        yield temporary
        # Concurrent replacements of one target can fail on Windows.
        with _replace_lock:
            temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def atomic_write_text(path: Path, text: str, encoding: str = "utf-8") -> None:
    with atomic_output_path(path) as temporary:
        temporary.write_text(text, encoding=encoding)
