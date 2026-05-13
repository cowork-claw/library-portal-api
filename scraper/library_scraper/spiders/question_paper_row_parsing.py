"""Table row and ASP.NET postback parsing helpers for the question-paper spider."""

import re
from urllib.parse import urljoin


class QuestionPaperRowParsingMixin:
    """Extract folder/PDF rows and ASP.NET form metadata from library pages."""

    def _extract_form_data(self, response):
        """Extract all form data needed for ASP.NET postback."""
        form_data = {}

        for field in response.css('input[type="hidden"]'):
            name = field.css("::attr(name)").get()
            value = field.css("::attr(value)").get("")
            if name:
                form_data[name] = value

        for field in response.css('input[type="text"], input[type="submit"], select'):
            name = field.css("::attr(name)").get()
            value = field.css("::attr(value)").get("")
            if name and name not in form_data:
                form_data[name] = value

        return form_data

    def _extract_items(self, response):
        """Extract all items from the current page."""
        items = []
        table = response.css('table[id*="gvFiles"]').get()
        if not table:
            self.logger.debug("No file table found with gvFiles ID")
            return items

        table_selector = response.css('table[id*="gvFiles"]')
        rows = table_selector.css("tr")[1:]
        self.logger.debug(f"Found table with {len(rows)} rows")

        for row in rows:
            item = self._extract_item_from_row(row, response)
            if item and item.get("name"):
                items.append(item)

        return items

    def _extract_item_from_row(self, row, response):
        """Extract item data from a table row."""
        cells = row.css("td")
        if len(cells) < 2:
            return None

        first_cell = cells[0]
        link_elem = first_cell.css("a")
        if not link_elem.get():
            return None

        name = self._extract_link_name(first_cell, link_elem)
        if not name or name in ["..", "."]:
            return None

        href = link_elem.css("::attr(href)").get("")
        link_id = link_elem.css("::attr(id)").get("")
        item_type = cells[1].css("::text").get("").strip()
        size = cells[3].css("::text").get("").strip() if len(cells) > 3 else ""
        is_folder, is_pdf, event_target, event_argument, pdf_url = self._classify_item(
            name, item_type, href, link_id, response
        )

        return {
            "name": name,
            "type": item_type,
            "size": size,
            "is_folder": is_folder,
            "is_pdf": is_pdf,
            "href": href,
            "event_target": event_target,
            "event_argument": event_argument,
            "pdf_url": pdf_url,
        }

    def _extract_link_name(self, first_cell, link_elem):
        """Extract display text from the table-row link."""
        full_text = "".join(first_cell.css("a ::text").getall()).strip()
        if full_text:
            return full_text

        link_html = link_elem.get()
        text_match = re.search(r"</?\w+[^>]*>\s*([^<]+)", link_html or "")
        return text_match.group(1).strip() if text_match else ""

    def _postback_target(self, href, link_id):
        """Extract ASP.NET postback navigation target from a link."""
        if "__doPostBack" not in href:
            return False, None, None

        postback_match = re.search(r"__doPostBack\('([^']+)','([^']*)'\)", href)
        if postback_match:
            return True, postback_match.group(1), postback_match.group(2)
        if link_id:
            return True, link_id, ""
        return False, None, None

    def _pdf_url(self, name_lower, item_type_lower, href, response):
        """Return a direct PDF URL when the row points at a PDF."""
        if ".pdf" not in name_lower and "pdf" not in item_type_lower:
            return False, None
        if not href or href.startswith("javascript:"):
            return True, None
        if href.startswith("http"):
            return True, href
        return True, urljoin(response.url, href)

    def _classify_item(self, name, item_type, href, link_id, response):
        """Classify a row as folder/PDF and extract navigation metadata."""
        name_lower = name.lower()
        item_type_lower = item_type.lower()
        is_folder, event_target, event_argument = self._postback_target(href, link_id)
        is_pdf, pdf_url = self._pdf_url(name_lower, item_type_lower, href, response)

        if not is_folder and not is_pdf:
            if "folder" in item_type_lower:
                is_folder = True
            elif "pdf" in item_type_lower:
                is_pdf = True

        return is_folder, is_pdf, event_target, event_argument, pdf_url
