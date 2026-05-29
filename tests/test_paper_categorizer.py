from pathlib import Path

from scripts.processing.paper_categorizer import PaperCategorizer, _write_paper_to_file
from scripts.processing.run_categorizer import StagingHandler


def _categorizer(tmp_path: Path) -> PaperCategorizer:
    data_dir = tmp_path / "data"
    (data_dir / "btech" / "branches").mkdir(parents=True)
    (data_dir / "btech" / "first_year").mkdir(parents=True)
    (data_dir / "bsc").mkdir(parents=True)
    return PaperCategorizer(data_dir)


def _relative_target(result, data_dir: Path) -> str:
    return result.target_file.relative_to(data_dir).as_posix()


def test_categorize_btech_branch_extracts_semester(tmp_path):
    categorizer = _categorizer(tmp_path)
    (categorizer.data_dir / "btech" / "branches" / "CSE.json").write_text("{}")

    result = categorizer._categorize({"course_code": "CSE2201", "program": "B.Tech"})

    assert result.category == "btech_branch"
    assert _relative_target(result, categorizer.data_dir) == "btech/branches/CSE.json"
    assert result.metadata_filled == {"degree_type": "B.Tech", "semester": 4}


def test_categorize_undergraduate_mechanical_is_not_masters(tmp_path):
    categorizer = _categorizer(tmp_path)
    (categorizer.data_dir / "btech" / "branches" / "Mechanical.json").write_text("{}")

    result = categorizer._categorize(
        {"course_code": "MEC2201", "program": "B.Tech Mechanical"}
    )

    assert result.category == "btech_branch"
    assert (
        _relative_target(result, categorizer.data_dir)
        == "btech/branches/Mechanical.json"
    )


def test_categorize_undergraduate_biomedical_is_not_masters(tmp_path):
    categorizer = _categorizer(tmp_path)
    (categorizer.data_dir / "btech" / "branches" / "Biomedical.json").write_text("{}")

    result = categorizer._categorize(
        {"course_code": "BME2201", "program": "Biomedical Engineering"}
    )

    assert result.category == "btech_branch"
    assert (
        _relative_target(result, categorizer.data_dir)
        == "btech/branches/Biomedical.json"
    )


def test_categorize_masters_degrees(tmp_path):
    categorizer = _categorizer(tmp_path)

    cases = (
        ({"course_code": "CSE5001", "program": "M.Tech"}, "mtech.json", "M.Tech"),
        ({"course_code": "MCA5001", "program": "MCA"}, "mca.json", "MCA"),
        ({"course_code": "ECE5001", "degree_type": "M.E"}, "me.json", "M.E"),
    )
    for paper, filename, degree_type in cases:
        result = categorizer._categorize(paper)
        assert result.category == "masters"
        assert _relative_target(result, categorizer.data_dir) == f"masters/{filename}"
        assert result.metadata_filled == {"degree_type": degree_type}


def test_categorize_first_year_streams(tmp_path):
    categorizer = _categorizer(tmp_path)

    cs_result = categorizer._categorize({"course_code": "CSS1001"})
    core_result = categorizer._categorize({"course_code": "MAT1171"})

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


def test_first_year_cs_stream_requires_02_suffix(tmp_path):
    categorizer = _categorizer(tmp_path)

    cs_result = categorizer._categorize({"course_code": "MAT1102"})
    non_cs_result = categorizer._categorize({"course_code": "MAT1109"})

    assert cs_result.category == "first_year_cs"
    assert non_cs_result.category != "first_year_cs"


def test_categorize_malformed_course_code_is_uncertain(tmp_path):
    categorizer = _categorizer(tmp_path)

    result = categorizer._categorize({"course_code": "1234"})

    assert result.category == "uncertain"
    assert result.target_file is None
    assert result.confidence == 0.1


def test_categorize_missing_branch_file_falls_back_to_other(tmp_path):
    categorizer = _categorizer(tmp_path)

    result = categorizer._categorize({"course_code": "CSE2201", "program": "B.Tech"})

    assert result.category == "other"
    assert _relative_target(result, categorizer.data_dir) == "other.json"
    assert "Branch file not found: CSE.json" in result.reasoning


def test_write_paper_replaces_wrong_shaped_target_file(tmp_path):
    target = tmp_path / "target.json"
    target.write_text("[]", encoding="utf-8")

    assert _write_paper_to_file(
        {"course_code": "CSE101", "url": "https://example.test/new.pdf"}, target
    )

    assert '"CSE101"' in target.read_text(encoding="utf-8")


def test_write_paper_replaces_malformed_course_bucket(tmp_path):
    target = tmp_path / "target.json"
    target.write_text('{"CSE101": "not a list"}', encoding="utf-8")

    assert _write_paper_to_file(
        {"course_code": "CSE101", "url": "https://example.test/new.pdf"}, target
    )

    assert '"https://example.test/new.pdf"' in target.read_text(encoding="utf-8")


def test_write_paper_skips_malformed_existing_entries(tmp_path):
    target = tmp_path / "target.json"
    target.write_text('{"CSE101": ["bad entry"]}', encoding="utf-8")

    assert _write_paper_to_file(
        {"course_code": "CSE101", "url": "https://example.test/new.pdf"}, target
    )


def test_staging_handler_recovers_from_wrong_shaped_file(tmp_path):
    staging_file = tmp_path / "pending_review.json"
    staging_file.write_text("[]", encoding="utf-8")

    handler = StagingHandler(staging_file)
    handler._add_paper(
        {"url": "https://example.test/a.pdf", "course_code": "CSE101"},
        0.2,
        ["low confidence"],
    )

    assert handler.data["papers"][0]["paper"]["url"] == "https://example.test/a.pdf"


def test_staging_handler_drops_malformed_staged_entries(tmp_path):
    staging_file = tmp_path / "pending_review.json"
    staging_file.write_text(
        '{"papers": ["bad", {"paper": "bad nested"}, {"paper": {"url": "old"}}]}',
        encoding="utf-8",
    )

    handler = StagingHandler(staging_file)
    handler._add_paper(
        {"url": "https://example.test/b.pdf", "course_code": "CSE102"},
        0.2,
        ["low confidence"],
    )

    assert [entry["paper"]["url"] for entry in handler.data["papers"]] == [
        "old",
        "https://example.test/b.pdf",
    ]
