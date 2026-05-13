import json

from scripts.processing.validate_data import validate_all, validate_json_file


def _write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _paper(url="https://example.test/paper.pdf", course_code="CSE101"):
    return {
        "url": url,
        "file_name": f"{course_code}.pdf",
        "course_code": course_code,
        "year": 2024,
        "semester": 3,
    }


def test_validate_json_file_accepts_valid_course_mapping(tmp_path):
    data_file = tmp_path / "CSE.json"
    _write_json(data_file, {"CSE101": [_paper()]})

    is_valid, errors = validate_json_file(data_file)

    assert is_valid is True
    assert errors == []


def test_validate_json_file_reports_record_errors(tmp_path):
    data_file = tmp_path / "CSE.json"
    _write_json(
        data_file,
        {
            "CSE101": [
                {
                    "url": "https://example.test/duplicate.pdf",
                    "file_name": "missing-code.pdf",
                    "year": 2031,
                    "semester": 11,
                },
                _paper("https://example.test/duplicate.pdf", "CSE101"),
            ]
        },
    )

    is_valid, errors = validate_json_file(data_file)

    assert is_valid is False
    assert "CSE101[0]: missing required field 'course_code'" in errors
    assert "CSE101[1]: duplicate URL" in errors
    assert "CSE101[0]: invalid year 2031" in errors
    assert "CSE101[0]: invalid semester 11" in errors


def test_validate_all_counts_files_papers_and_cross_file_duplicates(tmp_path):
    _write_json(tmp_path / "branches" / "CSE.json", {"CSE101": [_paper()]})
    _write_json(
        tmp_path / "branches" / "ECE.json",
        {"ECE101": [_paper(course_code="ECE101")]},
    )

    report = validate_all(tmp_path)

    assert report["valid"] is True
    assert report["files_checked"] == 2
    assert report["files_valid"] == 2
    assert report["files_invalid"] == 0
    assert report["total_papers"] == 2
    assert report["duplicate_urls"] == ["https://example.test/paper.pdf"]
    assert len(report["all_urls"]) == 1


def test_validate_all_reports_missing_directory(tmp_path):
    report = validate_all(tmp_path / "missing")

    assert report["valid"] is False
    assert report["error"] == "Data directory not found"
    assert report["files_checked"] == 0
