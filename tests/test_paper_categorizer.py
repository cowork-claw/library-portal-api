from pathlib import Path

from scripts.processing.paper_categorizer import PaperCategorizer


def _categorizer(tmp_path: Path) -> PaperCategorizer:
    data_dir = tmp_path / "data"
    (data_dir / "btech" / "branches").mkdir(parents=True)
    (data_dir / "btech" / "first_year").mkdir(parents=True)
    (data_dir / "bsc").mkdir(parents=True)
    return PaperCategorizer(data_dir, tmp_path / "staging")


def _relative_target(result, data_dir: Path) -> str:
    return result.target_file.relative_to(data_dir).as_posix()


def test_categorize_btech_branch_extracts_semester(tmp_path):
    categorizer = _categorizer(tmp_path)
    (categorizer.data_dir / "btech" / "branches" / "CSE.json").write_text("{}")

    result = categorizer.categorize({"course_code": "CSE2201", "program": "B.Tech"})

    assert result.category == "btech_branch"
    assert _relative_target(result, categorizer.data_dir) == "btech/branches/CSE.json"
    assert result.metadata_filled == {"degree_type": "B.Tech", "semester": 4}


def test_categorize_first_year_streams(tmp_path):
    categorizer = _categorizer(tmp_path)

    cs_result = categorizer.categorize({"course_code": "CSS1001"})
    core_result = categorizer.categorize({"course_code": "MAT1171"})

    assert cs_result.category == "first_year_cs"
    assert (
        _relative_target(cs_result, categorizer.data_dir)
        == "btech/first_year/cs_stream.json"
    )
    assert cs_result.metadata_filled == {"degree_type": "B.Tech", "streams": ["cs"]}
    assert core_result.category == "first_year_core"
    assert (
        _relative_target(core_result, categorizer.data_dir)
        == "btech/first_year/non_cs_stream.json"
    )
    assert core_result.metadata_filled == {"degree_type": "B.Tech", "streams": ["core"]}


def test_categorize_malformed_course_code_is_uncertain(tmp_path):
    categorizer = _categorizer(tmp_path)

    result = categorizer.categorize({"course_code": "1234"})

    assert result.category == "uncertain"
    assert result.target_file is None
    assert result.confidence == 0.1


def test_categorize_missing_branch_file_falls_back_to_other(tmp_path):
    categorizer = _categorizer(tmp_path)

    result = categorizer.categorize({"course_code": "CSE2201", "program": "B.Tech"})

    assert result.category == "other"
    assert _relative_target(result, categorizer.data_dir) == "other.json"
    assert "Branch file not found: CSE.json" in result.reasoning
