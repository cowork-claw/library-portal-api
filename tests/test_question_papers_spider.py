import sys
from pathlib import Path

from scrapy.http import HtmlResponse, Request

ROOT = Path(__file__).resolve().parents[1]
SCRAPER_DIR = ROOT / "scraper"
if str(SCRAPER_DIR) not in sys.path:
    sys.path.insert(0, str(SCRAPER_DIR))

from scraper.library_scraper.spiders.question_papers_enhanced import (  # noqa: E402
    QuestionPapersEnhancedSpider,
)


def _spider():
    return QuestionPapersEnhancedSpider.__new__(QuestionPapersEnhancedSpider)


def _response(row_html: str):
    request = Request("https://libportal.manipal.edu/MIT/Question%20Paper.aspx")
    return HtmlResponse(
        request.url,
        body=f"<table>{row_html}</table>".encode(),
        encoding="utf-8",
        request=request,
    )


def _row(response):
    return response.css("tr")[0]


def test_extract_item_from_row_returns_postback_folder():
    response = _response("""
        <tr>
          <td><a id="folderLink" href="javascript:__doPostBack('target','arg')">2026</a></td>
          <td>Folder</td><td></td><td></td>
        </tr>
        """)

    item = _spider()._extract_item_from_row(_row(response), response)

    assert item["name"] == "2026"
    assert item["is_folder"] is True
    assert item["is_pdf"] is False
    assert item["event_target"] == "target"
    assert item["event_argument"] == "arg"
    assert item["pdf_url"] is None


def test_extract_item_from_row_uses_link_id_for_malformed_postback():
    response = _response("""
        <tr>
          <td><a id="fallbackTarget" href="javascript:__doPostBack(bad)">CSE</a></td>
          <td>Folder</td><td></td><td></td>
        </tr>
        """)

    item = _spider()._extract_item_from_row(_row(response), response)

    assert item["is_folder"] is True
    assert item["event_target"] == "fallbackTarget"
    assert item["event_argument"] == ""


def test_extract_item_from_row_returns_relative_pdf_url():
    response = _response("""
        <tr>
          <td><a href="../RootFolder/2026/CSE101.pdf">CSE101.pdf</a></td>
          <td>PDF File</td><td></td><td>12 KB</td>
        </tr>
        """)

    item = _spider()._extract_item_from_row(_row(response), response)

    assert item["name"] == "CSE101.pdf"
    assert item["is_pdf"] is True
    assert item["is_folder"] is False
    assert item["size"] == "12 KB"
    assert item["pdf_url"] == "https://libportal.manipal.edu/RootFolder/2026/CSE101.pdf"


def test_extract_item_from_row_rejects_parent_directory_entries():
    response = _response("""
        <tr>
          <td><a href="javascript:__doPostBack('up','')">..</a></td>
          <td>Folder</td><td></td><td></td>
        </tr>
        """)

    assert _spider()._extract_item_from_row(_row(response), response) is None


def test_extract_metadata_populates_year_program_semester_and_subject():
    item = {
        "path": "2026 / B.Tech / III Sem",
        "file_name": "Algorithms (CSE 1071).pdf",
    }

    _spider()._extract_metadata(item)

    assert item["year"] == 2026
    assert item["program"] == " B.Tech "
    assert item["semester"] == 3
    assert item["subject"] == "Algorithms"
    assert item["course_code"] == "CSE1071"
    assert item["subject_code"] == "CSE1071"


def test_extract_metadata_recovers_year_from_text_path_component():
    item = {
        "path": "Question Papers 2026 / M.Tech / 2nd Sem",
        "file_name": "Advanced Topics (CSE 5071).pdf",
    }

    _spider()._extract_metadata(item)

    assert item["year"] == 2026
    assert item["program"] == " M.Tech "
    assert item["semester"] == 2
    assert item["subject"] == "Advanced Topics"
    assert item["course_code"] == "CSE5071"


def test_extract_metadata_supports_fourth_semester_roman_numeral():
    item = {"path": "2026 / B.Tech / IV Sem", "file_name": "Maths (MAT 2251).pdf"}

    _spider()._extract_metadata(item)

    assert item["semester"] == 4


def test_path_contains_target_year_respects_incremental_mode():
    spider = _spider()
    spider.current_year = 2026
    spider.is_incremental = True

    assert spider._path_contains_target_year("2026 / B.Tech") is True
    assert spider._path_contains_target_year("2024 / B.Tech") is False

    spider.is_incremental = False
    assert spider._path_contains_target_year("2024 / B.Tech") is True


def test_create_pdf_item_uses_parsed_pdf_url():
    response = _response("""
        <tr>
          <td><a href="../RootFolder/2026/CSE101.pdf">CSE101.pdf</a></td>
          <td>PDF File</td><td></td><td>12 KB</td>
        </tr>
        """)

    item = _spider()._create_pdf_item(
        {
            "is_pdf": True,
            "name": "PSUC (CSE 1071).pdf",
            "pdf_url": "https://libportal.manipal.edu/RootFolder/2026/CSE1071.pdf",
        },
        response,
    )

    assert item["url"] == "https://libportal.manipal.edu/RootFolder/2026/CSE1071.pdf"
    assert item["course_code"] == "CSE1071"


def test_create_pdf_item_reconstructs_url_when_link_href_missing():
    response = _response("""
        <tr>
          <td><a href="javascript:download()">CSE101.pdf</a></td>
          <td>PDF File</td><td></td><td>12 KB</td>
        </tr>
        """)

    item = _spider()._create_pdf_item(
        {"is_pdf": True, "name": "PSUC (CSE 1071).pdf", "pdf_url": None},
        response,
    )

    assert (
        item["url"]
        == "https://libportal.manipal.edu/RootFolder/PSUC%20%28CSE%201071%29.pdf"
    )
