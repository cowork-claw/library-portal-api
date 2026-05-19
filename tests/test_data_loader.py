import json
import tempfile
from pathlib import Path

from app_v2.data_loader import DataLoader


def test_data_loader_sanitizes_invalid_json_paths():
    with tempfile.TemporaryDirectory() as tmpdir:
        bad_file = Path(tmpdir) / "bad.json"
        bad_file.write_text("{not valid json", encoding="utf-8")

        loader = DataLoader(Path(tmpdir))
        loader._load_all()

        assert loader.stats.errors
        error = loader.stats.errors[0]
        assert "bad.json" in error
        assert tmpdir not in error


def test_data_loader_skips_malformed_paper_items_without_dropping_valid_items(tmp_path):
    data_file = tmp_path / "mixed.json"
    data_file.write_text(
        json.dumps(
            {
                "TEST101": [
                    "bad item",
                    {"url": "u1", "file_name": "paper.pdf", "course_code": "TEST101"},
                    42,
                    {"url": "u2", "file_name": "paper-2.pdf", "course_code": "TEST101"},
                ]
            }
        ),
        encoding="utf-8",
    )

    loader = DataLoader(tmp_path)
    papers = loader._load_all()

    assert [paper["url"] for paper in papers] == ["u1", "u2"]
    assert loader.stats.files_loaded == 1
    assert loader.stats.file_stats["mixed.json"]["papers"] == 2
    assert loader.stats.file_stats["mixed.json"]["courses"] == 1
    assert loader.stats.errors == [
        "Invalid paper in mixed.json TEST101[0]: str",
        "Invalid paper in mixed.json TEST101[2]: int",
    ]
