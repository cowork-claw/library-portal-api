import tempfile
from pathlib import Path

from app_v2.data_loader import DataLoader


def test_data_loader_sanitizes_invalid_json_paths():
    with tempfile.TemporaryDirectory() as tmpdir:
        bad_file = Path(tmpdir) / "bad.json"
        bad_file.write_text("{not valid json", encoding="utf-8")

        loader = DataLoader(Path(tmpdir))
        loader.load_all()

        assert loader.stats.errors
        error = loader.stats.errors[0]
        assert "bad.json" in error
        assert tmpdir not in error
