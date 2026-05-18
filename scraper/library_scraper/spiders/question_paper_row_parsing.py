import re
from urllib.parse import urljoin


class QuestionPaperRowParsingMixin:
    def _extract_form_data(self, response):
        form_data = {}

        for selector, overwrite in (
            ('input[type="hidden"]', True),
            ('input[type="text"], input[type="submit"], select', False),
        ):
            for field in response.css(selector):
                name = field.css("::attr(name)").get()
                if name and (overwrite or name not in form_data):
                    form_data[name] = field.css("::attr(value)").get("")

        return form_data

    def _extract_items(self, response):
        if not (table_selector := response.css('table[id*="gvFiles"]')).get():
            self.logger.debug("No file table found with gvFiles ID")
            return []

        rows = table_selector.css("tr")[1:]
        self.logger.debug(f"Found table with {len(rows)} rows")

        return [
            item
            for row in rows
            if (item := self._extract_item_from_row(row, response)) and item.get("name")
        ]

    def _extract_item_from_row(self, row, response):
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
        if full_text := "".join(first_cell.css("a ::text").getall()).strip():
            return full_text

        text_match = re.search(r"</?\w+[^>]*>\s*([^<]+)", link_elem.get() or "")
        return text_match.group(1).strip() if text_match else ""

    def _postback_target(self, href, link_id):
        if "__doPostBack" not in href:
            return False, None, None

        if postback_match := re.search(r"__doPostBack\('([^']+)','([^']*)'\)", href):
            return True, postback_match.group(1), postback_match.group(2)
        if link_id:
            return True, link_id, ""
        return False, None, None

    def _pdf_url(self, name_lower, item_type_lower, href, response):
        if ".pdf" not in name_lower and "pdf" not in item_type_lower:
            return False, None
        if not href or href.startswith("javascript:"):
            return True, None
        return True, href if href.startswith("http") else urljoin(response.url, href)

    def _classify_item(self, name, item_type, href, link_id, response):
        name_lower = name.lower()
        item_type_lower = item_type.lower()
        is_folder, event_target, event_argument = self._postback_target(href, link_id)
        is_pdf, pdf_url = self._pdf_url(name_lower, item_type_lower, href, response)

        if not is_folder and not is_pdf:
            is_folder = "folder" in item_type_lower
            is_pdf = not is_folder and "pdf" in item_type_lower

        return is_folder, is_pdf, event_target, event_argument, pdf_url
