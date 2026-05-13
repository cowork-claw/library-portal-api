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
    response = _response(
        """
        <tr>
          <td><a id="folderLink" href="javascript:__doPostBack('target','arg')">2026</a></td>
          <td>Folder</td><td></td><td></td>
        </tr>
        """
    )

    item = _spider().extract_item_from_row(_row(response), response)

    assert item["name"] == "2026"
    assert item["is_folder"] is True
    assert item["is_pdf"] is False
    assert item["event_target"] == "target"
    assert item["event_argument"] == "arg"
    assert item["pdf_url"] is None


def test_extract_item_from_row_uses_link_id_for_malformed_postback():
    response = _response(
        """
        <tr>
          <td><a id="fallbackTarget" href="javascript:__doPostBack(bad)">CSE</a></td>
          <td>Folder</td><td></td><td></td>
        </tr>
        """
    )

    item = _spider().extract_item_from_row(_row(response), response)

    assert item["is_folder"] is True
    assert item["event_target"] == "fallbackTarget"
    assert item["event_argument"] == ""


def test_extract_item_from_row_returns_relative_pdf_url():
    response = _response(
        """
        <tr>
          <td><a href="../RootFolder/2026/CSE101.pdf">CSE101.pdf</a></td>
          <td>PDF File</td><td></td><td>12 KB</td>
        </tr>
        """
    )

    item = _spider().extract_item_from_row(_row(response), response)

    assert item["name"] == "CSE101.pdf"
    assert item["is_pdf"] is True
    assert item["is_folder"] is False
    assert item["size"] == "12 KB"
    assert item["pdf_url"] == "https://libportal.manipal.edu/RootFolder/2026/CSE101.pdf"


def test_extract_item_from_row_rejects_parent_directory_entries():
    response = _response(
        """
        <tr>
          <td><a href="javascript:__doPostBack('up','')">..</a></td>
          <td>Folder</td><td></td><td></td>
        </tr>
        """
    )

    assert _spider().extract_item_from_row(_row(response), response) is None


def test_extract_metadata_populates_year_program_semester_and_subject():
    item = {
        "path": "2026 / B.Tech / III Sem",
        "file_name": "Algorithms (CSE).pdf",
    }

    _spider().extract_metadata(item)

    assert item["year"] == "2026"
    assert item["program"] == " B.Tech "
    assert item["semester"] == "III Sem"
    assert item["subject"] == "Algorithms"


def test_extract_metadata_recovers_year_from_text_path_component():
    item = {
        "path": "Question Papers 2026 / M.Tech / 2nd Sem",
        "file_name": "Advanced Topics.pdf",
    }

    _spider().extract_metadata(item)

    assert item["year"] == "2026"
    assert item["program"] == " M.Tech "
    assert item["semester"] == "2nd Sem"
    assert item["subject"] == "Advanced Topics"
