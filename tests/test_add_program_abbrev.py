import json

from scripts.add_program_abbrev import derive_abbrev, process_file


def test_derive_abbrev_falls_back_to_curriculum_branch() -> None:
    paper = {
        "course_code": "9999",
        "program": "",
        "curriculum_context": {"valid_for_branches": ["ECE"]},
    }

    assert derive_abbrev(paper, None) == "ECE"


def test_process_file_repairs_empty_valid_for_branches(tmp_path) -> None:
    data_file = tmp_path / "papers.json"
    data_file.write_text(
        json.dumps(
            {
                "CSE2201": [
                    {
                        "course_code": "CSE2201",
                        "program": "",
                        "curriculum_context": {"valid_for_branches": []},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    updated, errors = process_file(data_file, None)

    assert (updated, errors) == (1, 0)
    migrated = json.loads(data_file.read_text(encoding="utf-8"))
    paper = migrated["CSE2201"][0]
    assert paper["program_abbrev"] == "CSE"
    assert paper["curriculum_context"]["valid_for_branches"] == ["CSE"]
