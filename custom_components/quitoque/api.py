"""Asynchronous Quitoque web client and HTML parser."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import json
import logging
import re
import unicodedata
import zlib
from datetime import date, timedelta
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urljoin

from yarl import URL

from aiohttp import ClientError, ClientResponse, ClientResponseError, ClientSession

from .const import (
    BASE_URL,
    DASHBOARD_URL,
    LOGIN_CHECK_URL,
    LOGIN_URL,
    USER_AGENT,
)
from .models import (
    QuitoqueOrder,
    QuitoqueRecipe,
    QuitoqueRecipeDetails,
    QuitoqueRecipeStep,
)

_LOGGER = logging.getLogger(__name__)

_RECIPE_URL_RE = re.compile(
    r'href=["\'](?P<url>/personnaliser-ma-box/(?P<start>\d{4}-\d{2}-\d{2})/'
    r'(?P<end>\d{4}-\d{2}-\d{2})/(?:recettes|panier))["\']'
)


class QuitoqueError(Exception):
    """Base Quitoque error."""


class QuitoqueAuthenticationError(QuitoqueError):
    """The Quitoque credentials or web session are invalid."""


class QuitoqueParseError(QuitoqueError):
    """The expected Quitoque data could not be parsed."""


class _GtmDataParser(HTMLParser):
    """Extract Quitoque's JSON payload from the main-content element."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.payload: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "div" or self.payload is not None:
            return
        attributes = dict(attrs)
        if attributes.get("id") == "main-content":
            self.payload = attributes.get("data-gtm-gtm-data-value")


class _LoginFormParser(HTMLParser):
    """Extract the exact Quitoque login form fields."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.action: str | None = None
        self.in_login_form = False
        self.fields: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "form":
            action = attributes.get("action") or ""
            if action.endswith("/login-check"):
                self.in_login_form = True
                self.action = action
            return

        if tag != "input" or not self.in_login_form:
            return

        name = attributes.get("name")
        if name:
            self.fields[name] = attributes.get("value") or ""

    def handle_endtag(self, tag: str) -> None:
        if tag == "form" and self.in_login_form:
            self.in_login_form = False


class _ActiveWeeksParser(HTMLParser):
    """Extract active Quitoque weeks from dashboard switches."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.active_weeks: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "input":
            return
        attributes = dict(attrs)
        classes = (attributes.get("class") or "").split()
        week = attributes.get("data-gtm-week")
        if "switch" in classes and week and "checked" in attributes:
            self.active_weeks.add(week)


@dataclass(frozen=True, slots=True)
class _HistoricalOrderCard:
    """One order card from Quitoque's ordered-box history."""

    order_id: int
    delivery_date: date
    details_url: str
    recipe_names: tuple[str, ...]


class _HistoryLinkParser(HTMLParser):
    """Find the account link leading to ordered boxes/history."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._href: str | None = None
        self._text_parts: list[str] = []
        self.urls: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        self._href = dict(attrs).get("href")
        self._text_parts = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or self._href is None:
            return
        text = re.sub(r"\s+", " ", " ".join(self._text_parts)).strip().casefold()
        if (
            "box command" in text
            or "paniers command" in text
            or "commandes" == text
            or "historique" in text
        ):
            self.urls.append(urljoin(BASE_URL, self._href))
        self._href = None
        self._text_parts = []


_FRENCH_MONTHS = {
    "janvier": 1,
    "février": 2,
    "fevrier": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "août": 8,
    "aout": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "décembre": 12,
    "decembre": 12,
}


def _parse_french_delivery_date(value: str) -> date | None:
    """Parse labels such as 'Box du mercredi 26 août 2026'."""
    text = unescape(value).replace("\xa0", " ").strip().casefold()
    match = re.search(
        r"(?P<day>\d{1,2})\s+(?P<month>[a-zàâäéèêëîïôöùûüç]+)\s+(?P<year>\d{4})",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None
    month = _FRENCH_MONTHS.get(match.group("month").casefold())
    if month is None:
        return None
    try:
        return date(int(match.group("year")), month, int(match.group("day")))
    except ValueError:
        return None


class _HistoricalOrdersParser(HTMLParser):
    """Extract ordered-box cards, IDs, dates and recipe names."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._depth = 0
        self._card_depth: int | None = None
        self._date_capture = False
        self._date_parts: list[str] = []
        self._delivery_date: date | None = None
        self._details_url: str | None = None
        self._recipe_names: list[str] = []
        self.cards: list[_HistoricalOrderCard] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "div":
            self._depth += 1
            classes = set((attributes.get("class") or "").split())
            if self._card_depth is None and {"card", "list-order"}.issubset(classes):
                self._card_depth = self._depth
                self._delivery_date = None
                self._details_url = None
                self._recipe_names = []

        if self._card_depth is None:
            return

        modal_url = attributes.get("data-modal-url-param")
        if modal_url and "/order/" in modal_url and "/details" in modal_url:
            self._details_url = urljoin(BASE_URL, modal_url)

        if tag == "strong" and self._delivery_date is None:
            self._date_capture = True
            self._date_parts = []

        if tag == "img":
            name = (attributes.get("alt") or "").strip()
            if name and name not in self._recipe_names:
                self._recipe_names.append(name)

    def handle_data(self, data: str) -> None:
        if self._card_depth is not None and self._date_capture:
            self._date_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._card_depth is not None and tag == "strong" and self._date_capture:
            parsed = _parse_french_delivery_date(" ".join(self._date_parts))
            if parsed is not None and self._delivery_date is None:
                self._delivery_date = parsed
            self._date_capture = False
            self._date_parts = []

        if tag == "div":
            if self._card_depth is not None and self._depth == self._card_depth:
                self._finish_card()
            self._depth = max(0, self._depth - 1)

    def _finish_card(self) -> None:
        if self._delivery_date is not None and self._details_url:
            match = re.search(r"/order/(?P<order_id>\d+)/details", self._details_url)
            if match:
                self.cards.append(
                    _HistoricalOrderCard(
                        order_id=int(match.group("order_id")),
                        delivery_date=self._delivery_date,
                        details_url=self._details_url,
                        recipe_names=tuple(self._recipe_names),
                    )
                )
        self._card_depth = None
        self._delivery_date = None
        self._details_url = None
        self._recipe_names = []


def _stable_history_recipe_id(order_id: int, recipe_name: str) -> int:
    """Build a deterministic positive item id for history cards without GTM ids."""
    return zlib.crc32(f"{order_id}:{recipe_name}".encode("utf-8")) & 0x7FFFFFFF


def _extract_delivery_hours(html: str) -> tuple[int | None, int | None]:
    """Best-effort extraction of a delivery time range from an order recap."""
    text = _clean_recipe_text(html)
    patterns = (
        r"(?:créneau|horaire|livraison)[^\d]{0,80}(\d{1,2})\s*h(?:\s*\d{2})?\s*(?:-|à|–|—)\s*(\d{1,2})\s*h",
        r"(\d{1,2})\s*h(?:\s*\d{2})?\s*(?:-|à|–|—)\s*(\d{1,2})\s*h",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            start, end = int(match.group(1)), int(match.group(2))
            if 0 <= start <= 23 and 0 <= end <= 23:
                return start, end
    return None, None


def _duration_to_minutes(value: str) -> int | None:
    """Convert Quitoque duration labels such as '35 min', '1h' or '1h25'."""
    value = unescape(value).replace("\xa0", " ").strip().lower()

    hour_match = re.search(
        r"(?P<hours>\d+)\s*h(?:eure(?:s)?)?\s*(?P<minutes>\d{1,2})?",
        value,
        re.IGNORECASE,
    )
    if hour_match:
        return (
            int(hour_match.group("hours")) * 60
            + int(hour_match.group("minutes") or 0)
        )

    minute_match = re.search(
        r"(?P<minutes>\d+)\s*(?:min|minute(?:s)?)",
        value,
        re.IGNORECASE,
    )
    if minute_match:
        return int(minute_match.group("minutes"))

    return None


def _extract_recipe_durations(html: str) -> dict[int, int]:
    """Extract recipe preparation durations keyed by Quitoque item id."""
    durations: dict[int, int] = {}

    # Quitoque places the GTM recipe id on the recipe card. Search only inside
    # that card's local HTML window, then accept 35 min / 1h / 1h25 formats.
    id_matches = list(
        re.finditer(
            r'data-gtm-id=["\'](?P<item_id>\d+)["\']',
            html,
            re.IGNORECASE,
        )
    )

    for index, match in enumerate(id_matches):
        item_id = int(match.group("item_id"))
        block_end = (
            id_matches[index + 1].start()
            if index + 1 < len(id_matches)
            else min(len(html), match.start() + 12000)
        )
        block = html[match.start():block_end]

        duration_match = re.search(
            r'(?:recipe-duration[^>]*>.*?|dur[ée]e[^>]*>.*?)'
            r'(?P<duration>\d+\s*h(?:\s*\d+)?|\d+\s*min(?:ute)?s?)',
            block,
            re.IGNORECASE | re.DOTALL,
        )
        if not duration_match:
            # Fallback used by newer Quitoque cards where the duration class
            # disappeared but the duration remains visible in the card.
            duration_match = re.search(
                r'(?P<duration>\d+\s*h(?:\s*\d+)?|\d+\s*min(?:ute)?s?)',
                block[:5000],
                re.IGNORECASE,
            )

        if duration_match:
            minutes = _duration_to_minutes(duration_match.group("duration"))
            if minutes is not None:
                durations[item_id] = minutes

    return durations


def _extract_recipe_page_duration(html: str) -> int | None:
    """Extract the preparation duration from a public Quitoque recipe page."""
    visible = re.sub(
        r"<(script|style|noscript)\b[^>]*>.*?</\1>",
        " ",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    text = _clean_recipe_text(visible)
    match = re.search(
        r"(?P<duration>\d+\s*h(?:\s*\d+)?|\d+\s*min(?:ute)?s?)\s*(?:En cuisine|Préparation)",
        text,
        re.IGNORECASE,
    )
    if match:
        return _duration_to_minutes(match.group("duration"))
    match = re.search(
        r"(?P<duration>\d+\s*h(?:\s*\d+)?|\d+\s*min(?:ute)?s?)",
        text[:2500],
        re.IGNORECASE,
    )
    return _duration_to_minutes(match.group("duration")) if match else None


def _recipe_slug(name: str) -> str:
    """Build the public Quitoque recipe slug used by /recettes/<slug>."""
    normalized = unicodedata.normalize("NFKD", name)
    ascii_name = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    ascii_name = ascii_name.replace("’", "-").replace("'", "-").replace("&", " et ")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_name).strip("-").lower()
    return slug


class _RecipeUrlParser(HTMLParser):
    """Extract Quitoque recipe detail URLs keyed by GTM recipe id."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.urls: dict[int, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        attributes = dict(attrs)
        href = attributes.get("href") or ""
        item_id = attributes.get("data-gtm-id")
        if not item_id:
            return
        if "/recettes/" not in href and "/products/" not in href:
            return
        try:
            self.urls[int(item_id)] = urljoin(BASE_URL, href)
        except (TypeError, ValueError):
            return


def _clean_recipe_text(value: str) -> str:
    """Normalize text extracted from recipe HTML/JSON."""
    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.IGNORECASE)
    value = re.sub(r"<[^>]+>", " ", value)
    value = unescape(value).replace("\xa0", " ")
    return re.sub(r"\s+", " ", value).strip()


def _extract_json_ld_recipe_steps(html: str) -> tuple[QuitoqueRecipeStep, ...]:
    """Extract Recipe instructions from schema.org JSON-LD when available."""
    scripts = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html,
        re.IGNORECASE | re.DOTALL,
    )

    def walk(value):
        if isinstance(value, dict):
            if value.get("@type") == "Recipe":
                yield value
            for child in value.values():
                yield from walk(child)
        elif isinstance(value, list):
            for child in value:
                yield from walk(child)

    for raw in scripts:
        try:
            payload = json.loads(unescape(raw).strip())
        except (json.JSONDecodeError, TypeError):
            continue

        for recipe_data in walk(payload):
            instructions = recipe_data.get("recipeInstructions")
            if not instructions:
                continue

            steps: list[QuitoqueRecipeStep] = []
            items = instructions if isinstance(instructions, list) else [instructions]
            number = 1

            for item in items:
                if isinstance(item, str):
                    instruction = _clean_recipe_text(item)
                    if instruction:
                        steps.append(
                            QuitoqueRecipeStep(
                                number=number,
                                title=f"Étape {number}",
                                instructions=(instruction,),
                            )
                        )
                        number += 1
                    continue

                if not isinstance(item, dict):
                    continue

                if item.get("@type") == "HowToSection":
                    for child in item.get("itemListElement", []):
                        if not isinstance(child, dict):
                            continue
                        instruction = _clean_recipe_text(
                            str(child.get("text") or child.get("name") or "")
                        )
                        if instruction:
                            steps.append(
                                QuitoqueRecipeStep(
                                    number=number,
                                    title=_clean_recipe_text(
                                        str(child.get("name") or f"Étape {number}")
                                    ),
                                    instructions=(instruction,),
                                )
                            )
                            number += 1
                    continue

                instruction = _clean_recipe_text(
                    str(item.get("text") or item.get("description") or "")
                )
                title = _clean_recipe_text(
                    str(item.get("name") or f"Étape {number}")
                )
                if instruction:
                    steps.append(
                        QuitoqueRecipeStep(
                            number=number,
                            title=title,
                            instructions=(instruction,),
                        )
                    )
                    number += 1

            if steps:
                return tuple(steps)

    return ()


def _extract_recipe_steps(html: str) -> tuple[QuitoqueRecipeStep, ...]:
    """Extract only the actual cooking steps from a Quitoque recipe page."""
    json_steps = _extract_json_ld_recipe_steps(html)
    if json_steps:
        return json_steps

    cleaned = re.sub(
        r"(?i)</(?:p|li|div|h[1-6]|section|article)>",
        "\n",
        html,
    )
    cleaned = re.sub(r"(?i)<br\s*/?>", "\n", cleaned)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = unescape(cleaned).replace("\xa0", " ")

    lines = [
        re.sub(r"\s+", " ", line).strip()
        for line in cleaned.splitlines()
    ]

    stop_markers = (
        "les gestes de cuisine",
        "valeurs nutritionnelles",
        "le nutri-score",
        "le nutri score",
        "le score carbone",
        "score carbone",
        "ajouter à ma box",
        "aide et contact",
        "questions fréquentes",
        "offres et services",
    )

    def is_noise(line: str) -> bool:
        lowered = line.lower()
        return (
            not line
            or "classlist." in lowered
            or "product#fetch" in lowered
            or "click->" in lowered
            or "data-product-" in lowered
            or "data-gtm-" in lowered
            or lowered.startswith("data-")
            or lowered in {"voir toute la recette", "voir plus"}
        )

    step_re = re.compile(
        r"^(?:Étape\s+)?(?P<number>\d+)"
        r"(?:\s*[.:\-–—]\s*(?P<title>.*))?$",
        re.IGNORECASE,
    )

    steps: list[QuitoqueRecipeStep] = []
    current_number: int | None = None
    current_title = ""
    instructions: list[str] = []

    def flush() -> None:
        nonlocal current_number, current_title, instructions
        if current_number is None:
            return
        cleaned_instructions = tuple(
            instruction for instruction in instructions if instruction
        )
        if cleaned_instructions:
            steps.append(
                QuitoqueRecipeStep(
                    number=current_number,
                    title=current_title or f"Étape {current_number}",
                    instructions=cleaned_instructions,
                )
            )
        current_number = None
        current_title = ""
        instructions = []

    for line in lines:
        if is_noise(line):
            continue

        lowered = line.lower()
        if any(lowered.startswith(marker) for marker in stop_markers):
            if current_number is not None:
                flush()
                break
            continue

        match = step_re.match(line)
        if match:
            number = int(match.group("number"))
            if 1 <= number <= 20:
                flush()
                current_number = number
                current_title = (match.group("title") or "").strip()
                continue

        if current_number is not None:
            instructions.append(line.lstrip("-• ").strip())

    flush()
    return tuple(steps)


class _RecipePageMetadataParser(HTMLParser):
    """Extract the main image of a Quitoque recipe page."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.image_url: str | None = None
        self.fallback_image_url: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)

        if tag == "meta":
            key = (
                attributes.get("property")
                or attributes.get("name")
                or ""
            ).lower()
            content = attributes.get("content")
            if key in {"og:image", "twitter:image", "twitter:image:src"} and content:
                self.image_url = content
                return

        if tag != "img" or self.image_url is not None:
            return

        src = (
            attributes.get("src")
            or attributes.get("data-src")
            or attributes.get("data-lazy-src")
        )
        if not src:
            return

        lowered = src.lower()
        css_class = (attributes.get("class") or "").lower()
        alt = (attributes.get("alt") or "").lower()

        if (
            "recipe" in css_class
            or "product" in css_class
            or "image-repository" in lowered
            or "recette" in alt
        ):
            self.fallback_image_url = src

    @property
    def best_image_url(self) -> str | None:
        return self.image_url or self.fallback_image_url


def _extract_recipe_image_url(html: str, base_url: str) -> str | None:
    """Extract the main recipe image URL from the Quitoque page."""
    parser = _RecipePageMetadataParser()
    parser.feed(html)
    if parser.best_image_url:
        return urljoin(base_url, parser.best_image_url)

    scripts = re.findall(
        r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
        html,
        re.IGNORECASE | re.DOTALL,
    )

    def find_recipe(value):
        if isinstance(value, dict):
            if value.get("@type") == "Recipe":
                return value
            for child in value.values():
                found = find_recipe(child)
                if found:
                    return found
        elif isinstance(value, list):
            for child in value:
                found = find_recipe(child)
                if found:
                    return found
        return None

    for raw in scripts:
        try:
            payload = json.loads(unescape(raw).strip())
        except (json.JSONDecodeError, TypeError):
            continue

        recipe = find_recipe(payload)
        if not recipe:
            continue

        image = recipe.get("image")
        if isinstance(image, list) and image:
            image = image[0]
        if isinstance(image, dict):
            image = image.get("url") or image.get("contentUrl")
        if isinstance(image, str) and image:
            return urljoin(base_url, image)

    return None




_EQUIPMENT_TERMS = {
    "sauteuse", "poêle", "poele", "fouet", "casserole", "passoire",
    "saladier", "mixeur", "blender", "économe", "econome", "spatule",
    "râpe", "rape", "four", "plaque", "couteau", "planche", "bol",
    "ramequin", "moule", "louche", "écumoire", "ecumoire", "pince",
    "cuillère en bois", "cuillere en bois", "presse-ail", "presse ail",
    "papier cuisson", "papier sulfurisé", "papier sulfurise",
}

_KITCHEN_STAPLE_TERMS = {
    "sel", "poivre", "huile d'olive", "huile", "eau", "beurre",
    "sucre", "farine", "vinaigre", "moutarde", "miel",
}


def _normalise_visible_line(value: str) -> str:
    """Normalize one visible line from the Quitoque recipe page."""
    value = unescape(value).replace("\xa0", " ")
    value = re.sub(r"\s+", " ", value).strip(" \t\r\n•·-")
    return value.strip()


def _is_equipment_item(value: str) -> bool:
    """Return True when a visible recipe item is cooking equipment."""
    lowered = value.casefold().strip()
    if not lowered:
        return False
    if lowered in {"équipement", "equipement", "matériel", "materiel"}:
        return False
    return any(
        lowered == term or lowered.startswith(term + " ") or lowered.endswith(" " + term)
        for term in _EQUIPMENT_TERMS
    )


def _is_kitchen_staple(value: str) -> bool:
    """Return True for pantry items normally supplied by the customer."""
    lowered = value.casefold().strip()
    if not lowered:
        return False
    # Quantity-prefixed pantry entries, e.g. "2 càs eau".
    normalized = re.sub(
        r"^(?:\d+(?:[.,]\d+)?|qq)\s*(?:x|g|kg|ml|cl|l|càs|cas|c\.?\s*à\s*soupe|càc|cac)?\s*",
        "",
        lowered,
    ).strip()
    return any(
        normalized == term
        or normalized.startswith(term + " ")
        or term in {"huile", "eau"} and term in normalized
        for term in _KITCHEN_STAPLE_TERMS
    )


def _visible_items_from_block(block: str) -> tuple[str, ...]:
    """Extract short visible list-like items from an HTML fragment."""
    values: list[str] = []

    # Prefer actual list items.
    for raw in re.findall(r"<li\b[^>]*>(.*?)</li>", block, re.I | re.S):
        value = _normalise_visible_line(re.sub(r"<[^>]+>", " ", raw))
        if value and value not in values:
            values.append(value)

    # Quitoque occasionally renders recipe data with div/p/span nodes rather
    # than <li>. Fall back to block-level text lines when the list is sparse.
    if len(values) < 2:
        line_html = re.sub(
            r"</?(?:div|p|span|section|article|h[1-6]|ul|ol|br)\b[^>]*>",
            "\n",
            block,
            flags=re.I,
        )
        for raw in re.sub(r"<[^>]+>", " ", line_html).splitlines():
            value = _normalise_visible_line(raw)
            if not value or value in values:
                continue
            if len(value) > 140:
                continue
            values.append(value)

    cleaned: list[str] = []
    for value in values:
        lowered = value.casefold()
        if lowered in {
            "ingrédient", "ingrédients", "ingredient", "ingredients",
            "dans votre box", "dans votre cuisine",
            "équipement", "equipement", "matériel", "materiel",
        }:
            continue
        if any(
            marker in lowered
            for marker in (
                "allerg", "composition", "conservation", "mode d'emploi",
                "window.", "function(", "kameleoon", "googletag",
                "valeurs nutritionnelles", "nutri-score", "score carbone",
            )
        ):
            continue
        if value not in cleaned:
            cleaned.append(value)

    return tuple(cleaned)




class _QuitoqueRecipeSectionsParser(HTMLParser):
    """Parse Quitoque's explicit recipe tabs and lists.

    Observed Quitoque DOM:
      #ingredients ul.ingredient-list -> ingredients supplied in the box
      #ingredients ul.kitchen-list    -> "Dans votre cuisine"
      #equipment ul.ingredient-list   -> equipment
    """

    _VOID_TAGS = {
        "area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._stack: list[dict[str, object]] = []
        self._section: str | None = None
        self._list_kind: str | None = None
        self._li_parts: list[str] | None = None
        self._li_kind: str | None = None

        self.box_ingredients: list[str] = []
        self.kitchen_ingredients: list[str] = []
        self.equipment: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        attributes = dict(attrs)
        previous_section = self._section
        previous_list_kind = self._list_kind

        element_id = attributes.get("id")
        if element_id == "ingredients":
            self._section = "ingredients"
        elif element_id == "equipment":
            self._section = "equipment"

        if tag == "ul":
            classes = set((attributes.get("class") or "").split())
            if "kitchen-list" in classes:
                self._list_kind = "kitchen"
            elif "ingredient-list" in classes:
                if self._section == "equipment":
                    self._list_kind = "equipment"
                elif self._section == "ingredients":
                    self._list_kind = "box"

        if tag == "li" and self._list_kind in {"box", "kitchen", "equipment"}:
            self._li_parts = []
            self._li_kind = self._list_kind

        if tag not in self._VOID_TAGS:
            self._stack.append(
                {
                    "tag": tag,
                    "previous_section": previous_section,
                    "previous_list_kind": previous_list_kind,
                }
            )

    def handle_endtag(self, tag: str) -> None:
        if tag == "li" and self._li_parts is not None and self._li_kind:
            value = _normalise_visible_line(" ".join(self._li_parts))
            if value:
                target = {
                    "box": self.box_ingredients,
                    "kitchen": self.kitchen_ingredients,
                    "equipment": self.equipment,
                }[self._li_kind]
                if value not in target:
                    target.append(value)
            self._li_parts = None
            self._li_kind = None

        # Restore state from the matching open element. HTML from Quitoque is
        # well formed, but search backwards to remain tolerant of odd markup.
        for index in range(len(self._stack) - 1, -1, -1):
            frame = self._stack[index]
            if frame["tag"] == tag:
                self._section = frame["previous_section"]  # type: ignore[assignment]
                self._list_kind = frame["previous_list_kind"]  # type: ignore[assignment]
                del self._stack[index:]
                break

    def handle_data(self, data: str) -> None:
        if self._li_parts is not None:
            value = data.strip()
            if value:
                self._li_parts.append(value)


def _extract_exact_recipe_lists(
    html: str,
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """Extract the three recipe lists from Quitoque's explicit DOM sections."""
    parser = _QuitoqueRecipeSectionsParser()
    parser.feed(html)
    return (
        tuple(parser.box_ingredients),
        tuple(parser.kitchen_ingredients),
        tuple(parser.equipment),
    )


def _split_recipe_lists_from_html(
    html: str,
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """Extract box ingredients, kitchen staples and equipment.

    Quitoque's explicit DOM structure is authoritative. The legacy heuristic is
    only used as a fallback for older/alternate page layouts.
    """
    exact_box, exact_kitchen, exact_equipment = _extract_exact_recipe_lists(html)

    # If the modern Quitoque structure is present, never reclassify by words:
    # #ingredients and #equipment already tell us exactly what each item is.
    if exact_box or exact_kitchen or exact_equipment:
        return exact_box, exact_kitchen, exact_equipment

    # Legacy fallback for older Quitoque HTML.
    visible_html = re.sub(
        r"<(script|style|noscript)\b[^>]*>.*?</\1>",
        " ",
        html,
        flags=re.I | re.S,
    )

    candidates: list[str] = []
    for match in re.finditer(r"Ingr[ée]dients?", visible_html, re.I):
        tail = visible_html[match.end():]
        end_match = re.search(r"(?:[ÉE]tape\s*1|Préparation)", tail, re.I)
        if not end_match:
            continue
        block = tail[:end_match.start()]
        if len(block) <= 20000:
            candidates.append(block)

    if not candidates:
        return (), (), ()

    def candidate_score(block: str) -> int:
        li_count = len(re.findall(r"<li\b", block, re.I))
        quantity_count = len(
            re.findall(
                r"\b(?:\d+(?:[.,]\d+)?\s*(?:x|g|kg|ml|cl|l|càs|cas|càc|cac)|qq\s+)",
                _normalise_visible_line(re.sub(r"<[^>]+>", " ", block)),
                re.I,
            )
        )
        return li_count * 3 + quantity_count * 2

    section_html = max(candidates, key=candidate_score)
    candidates_values = _visible_items_from_block(section_html)

    box: list[str] = []
    kitchen: list[str] = []
    equipment: list[str] = []
    for value in candidates_values:
        if _is_equipment_item(value):
            equipment.append(value)
        elif _is_kitchen_staple(value):
            kitchen.append(value)
        else:
            box.append(value)

    return tuple(box), tuple(kitchen), tuple(equipment)


def _extract_recipe_structured_data(
    html: str,
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...], str | None]:
    """Extract box ingredients, kitchen ingredients, equipment and serving count."""

    def clean(value: object) -> str:
        return re.sub(r"\s+", " ", unescape(str(value))).strip()

    def ingredient_text(value: object) -> str | None:
        if isinstance(value, str):
            text = clean(value)
            return text or None
        if not isinstance(value, dict):
            return None
        name = next((clean(value[k]) for k in (
            "name", "label", "title", "ingredientName", "productName"
        ) if value.get(k)), "")
        quantity = next((clean(value[k]) for k in (
            "quantity", "qty", "amount", "value"
        ) if value.get(k) not in (None, "")), "")
        unit = next((clean(value[k]) for k in (
            "unit", "unitName", "measurementUnit", "measure"
        ) if value.get(k)), "")
        if not name:
            for key in ("ingredient", "product", "food"):
                nested = value.get(key)
                if isinstance(nested, dict):
                    nested_name = ingredient_text(nested)
                    if nested_name:
                        name = nested_name
                        break
                elif nested:
                    name = clean(nested)
                    break
        if not name:
            return None
        prefix = " ".join(part for part in (quantity, unit) if part)
        return f"{prefix} {name}".strip() if prefix else name

    def parse_collection(value: object) -> tuple[str, ...]:
        if isinstance(value, (str, dict)):
            value = [value]
        if not isinstance(value, list):
            return ()
        result: list[str] = []
        for item in value:
            text = ingredient_text(item)
            if text and text not in result:
                result.append(text)
        return tuple(result)

    ingredient_keys = {
        "recipeIngredient", "recipeIngredients", "ingredients", "ingredientList",
        "ingredient_list", "products", "productsList",
    }
    serving_keys = {
        "recipeYield", "servings", "serving", "portions", "portion",
        "numberOfServings", "number_of_servings", "people", "persons",
        "personCount", "guestCount", "numberOfPeople", "peopleCount",
    }
    best_ingredients: tuple[str, ...] = ()
    best_kitchen_ingredients: tuple[str, ...] = ()
    best_equipment: tuple[str, ...] = ()
    best_servings: str | None = None

    def normalise_servings(raw: object) -> str | None:
        if isinstance(raw, list) and raw:
            raw = raw[0]
        if isinstance(raw, dict):
            raw = raw.get("value") or raw.get("label") or raw.get("name")
        if raw in (None, ""):
            return None
        text = clean(raw)
        if not text:
            return None
        match = re.search(r"\b(\d{1,2})\b", text)
        if match:
            return f"{match.group(1)} personnes"
        return text

    def walk(value: object) -> None:
        nonlocal best_ingredients, best_servings
        if isinstance(value, dict):
            for key, child in value.items():
                if key in ingredient_keys:
                    parsed = parse_collection(child)
                    if len(parsed) > len(best_ingredients):
                        best_ingredients = parsed
                if key in serving_keys and best_servings is None:
                    best_servings = normalise_servings(child)
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    scripts = re.findall(
        r"<script[^>]+type=[\"'](?:application/ld\+json|application/json)[\"'][^>]*>(.*?)</script>",
        html, re.IGNORECASE | re.DOTALL,
    )
    for raw in scripts:
        try:
            walk(json.loads(unescape(raw).strip()))
        except (json.JSONDecodeError, TypeError):
            continue

    for match in re.finditer(r"\bdata-[\w:-]+=[\"'](?P<value>[^\"']+)[\"']", html, re.I):
        raw = unescape(match.group("value")).strip()
        if raw.startswith(("{", "[")):
            try:
                walk(json.loads(raw))
            except (json.JSONDecodeError, TypeError):
                pass

    # Build a text-only copy of the page for the serving fallback.
    visible_html = re.sub(
        r"<(script|style|noscript)\b[^>]*>.*?</\1>",
        " ",
        html,
        flags=re.I | re.S,
    )
    visible_text = clean(re.sub(r"<[^>]+>", " ", visible_html))

    if best_servings is None:
        for pattern in (
            r"(?:pour|prévu(?:e)?\s+pour)\s*(\d{1,2})\s*personnes?",
            r"(\d{1,2})\s*personnes?",
            r"(\d{1,2})\s*portions?",
        ):
            match = re.search(pattern, visible_text, re.I)
            if match:
                best_servings = f"{match.group(1)} personnes"
                break

    html_box, html_kitchen, html_equipment = _split_recipe_lists_from_html(html)

    # Visible recipe lists are preferred because they preserve Quitoque's
    # displayed quantities. Structured JSON remains the fallback when a page
    # uses a different HTML layout.
    if html_box:
        best_ingredients = html_box
    if html_kitchen:
        best_kitchen_ingredients = html_kitchen
    if html_equipment:
        best_equipment = html_equipment

    # If the visible page had no explicit "Dans votre cuisine" heading,
    # separate obvious pantry staples/equipment from a JSON ingredient list.
    if best_ingredients:
        final_box: list[str] = []
        final_kitchen = list(best_kitchen_ingredients)
        final_equipment = list(best_equipment)

        for value in best_ingredients:
            lowered = value.casefold().strip()
            if lowered in {
                "équipement", "equipement", "matériel", "materiel",
                "ingrédient", "ingrédients",
            }:
                continue
            if _is_equipment_item(value):
                if value not in final_equipment:
                    final_equipment.append(value)
            elif _is_kitchen_staple(value) and not best_kitchen_ingredients:
                if value not in final_kitchen:
                    final_kitchen.append(value)
            else:
                if value not in final_box:
                    final_box.append(value)

        best_ingredients = tuple(final_box)
        best_kitchen_ingredients = tuple(final_kitchen)
        best_equipment = tuple(final_equipment)

    return best_ingredients, best_kitchen_ingredients, best_equipment, best_servings


class QuitoqueClient:
    """Fetch the current order using Quitoque credentials."""

    def __init__(
        self,
        session: ClientSession,
        username: str,
        password: str,
        recipes_url: str | None = None,
    ) -> None:
        self._session = session
        self._username = username.strip()
        self._password = password
        self._configured_recipes_url = recipes_url.strip() if recipes_url else None
        self._authenticated = False
        self._auth_event_callback: Callable[[str], None] | None = None

    def set_auth_event_callback(
        self,
        callback: Callable[[str], None] | None,
    ) -> None:
        """Register a callback for successful login/relogin events."""
        self._auth_event_callback = callback

    def _emit_auth_event(self, event: str) -> None:
        """Emit an authentication event without coupling the API to HA."""
        if self._auth_event_callback is not None:
            self._auth_event_callback(event)

    async def _async_auto_reconnect(self) -> None:
        """Perform one automatic reauthentication attempt."""
        _LOGGER.info(
            "Session Quitoque expirée : tentative de reconnexion automatique"
        )
        self._authenticated = False
        await self.async_login(auto_reconnect=True)
        _LOGGER.info("Reconnexion automatique Quitoque réussie")

    async def async_get_order(self) -> QuitoqueOrder | None:
        """Return the next active Quitoque order."""
        orders = await self.async_get_orders()
        return orders[0] if orders else None

    async def async_get_orders(self) -> tuple[QuitoqueOrder, ...]:
        """Return all active future Quitoque orders.

        A normal web-session expiration is handled transparently: the client
        logs in again once and replays the complete request. Only a failed
        fresh login is surfaced as an authentication error to Home Assistant.
        """
        if not self._authenticated:
            await self.async_login()

        try:
            return await self._async_get_orders_authenticated()
        except QuitoqueAuthenticationError:
            await self._async_auto_reconnect()
            # Exactly one retry: never loop on invalid credentials/site changes.
            return await self._async_get_orders_authenticated()

    async def _async_get_orders_authenticated(
        self,
    ) -> tuple[QuitoqueOrder, ...]:
        """Return Quitoque orders from S0 through S+4.

        S0/S+1 are read from the ordered-box history, while S+2/S+3/S+4
        continue to come from the active planning dashboard. Orders are merged
        by their stable Quitoque order id so a box can move from S+2 to S0
        without ever becoming a duplicate.
        """
        if self._configured_recipes_url:
            recipes_urls = (self._configured_recipes_url,)
        else:
            recipes_urls = await self._async_discover_recipes_urls()

        orders_by_id: dict[int, QuitoqueOrder] = {}

        for recipes_url in recipes_urls:
            order = await self._async_get_order_from_url(recipes_url)
            orders_by_id[order.order_id] = order

        if not self._configured_recipes_url:
            for order in await self._async_discover_recent_history_orders():
                # Prefer the fully structured planning-page order when Quitoque
                # temporarily exposes the same order in both places.
                orders_by_id.setdefault(order.order_id, order)

        orders = sorted(orders_by_id.values(), key=lambda order: order.delivery_date)
        _LOGGER.debug(
            "Box Quitoque S0 à S+4 récupérées : %s",
            [
                f"{order.order_id}:{order.delivery_date.isoformat()}"
                for order in orders
            ],
        )
        return tuple(orders)

    async def _async_get_order_from_url(self, recipes_url: str) -> QuitoqueOrder:
        """Fetch and parse one Quitoque order page."""
        html, final_url = await self._async_get_text(recipes_url)

        if self._looks_like_login_page(html, final_url):
            self._authenticated = False
            raise QuitoqueAuthenticationError(
                "La session Quitoque a expiré"
            )

        return self._parse_order(html, recipes_url)

    async def async_login(self, *, auto_reconnect: bool = False) -> None:
        """Authenticate using Quitoque's exact HTML form and CSRF token."""
        # Chrome already sends the client-side "login=1" cookie when requesting
        # /login. Set it BEFORE fetching the login page so the PHP session and
        # CSRF token are generated in the same cookie context as the browser.
        self._session.cookie_jar.update_cookies(
            {"login": "1"},
            response_url=URL(BASE_URL),
        )

        # A fresh login page and the PHP session cookie must come from the same
        # private ClientSession that submits /login-check.
        login_html, login_final_url = await self._async_get_text(LOGIN_URL)
        parser = _LoginFormParser()
        parser.feed(login_html)

        csrf_token = parser.fields.get("_csrf_shop_security_token")
        if not parser.action or not csrf_token:
            raise QuitoqueParseError(
                "Jeton CSRF ou formulaire de connexion introuvable"
            )

        cookie_names = sorted(cookie.key for cookie in self._session.cookie_jar)
        _LOGGER.debug("Cookies reçus avant connexion Quitoque : %s", cookie_names)

        data = {
            "_username": self._username,
            "_password": self._password,
            "_csrf_shop_security_token": csrf_token,
        }
        action = urljoin(login_final_url, parser.action or LOGIN_CHECK_URL)

        outgoing_cookies = self._session.cookie_jar.filter_cookies(action)
        _LOGGER.debug(
            "Envoi Quitoque : username_length=%s password_length=%s "
            "csrf_length=%s cookies=%s",
            len(self._username),
            len(self._password),
            len(csrf_token),
            sorted(outgoing_cookies),
        )

        headers = self._headers()
        headers.update(
            {
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;q=0.9,"
                    "image/avif,image/webp,image/apng,*/*;q=0.8,"
                    "application/signed-exchange;v=b3;q=0.7"
                ),
                "Cache-Control": "max-age=0",
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": BASE_URL,
                "Referer": login_final_url,
                "Sec-CH-UA": (
                    '"Not;A=Brand";v="8", "Chromium";v="150", '
                    '"Google Chrome";v="150"'
                ),
                "Sec-CH-UA-Mobile": "?0",
                "Sec-CH-UA-Platform": '"macOS"',
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "same-origin",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1",
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/150.0.0.0 Safari/537.36"
                ),
            }
        )

        try:
            # Do not follow immediately: a successful Symfony Security login
            # normally answers with a redirect. Inspecting it avoids mistaking
            # the redirected page for a successful authentication.
            async with self._session.post(
                action,
                data=data,
                headers=headers,
                allow_redirects=False,
                timeout=30,
            ) as response:
                response_text = await response.text(errors="replace")
                status = response.status
                location = response.headers.get("Location")
                final_url = str(response.url)

            auth_cookies = self._session.cookie_jar.filter_cookies(BASE_URL)
            is_logged = auth_cookies.get("is_logged")
            is_logged_value = is_logged.value if is_logged is not None else None

            _LOGGER.debug(
                "Réponse Quitoque /login-check : status=%s location=%s cookies=%s "
                "is_logged=%s",
                status,
                location,
                sorted(cookie.key for cookie in self._session.cookie_jar),
                is_logged_value,
            )

            if status in {401, 403}:
                raise QuitoqueAuthenticationError("Connexion Quitoque refusée")

            if status not in {200, 301, 302, 303, 307, 308}:
                raise QuitoqueError(
                    f"Réponse inattendue de Quitoque : HTTP {status}"
                )

            # Quitoque redirects to /login even on a successful authentication.
            # The reliable server-side marker is the HttpOnly cookie
            # `is_logged=1`, set by the successful POST /login-check response.
            if is_logged_value != "1":
                error_message = self._extract_login_error(response_text)

                _LOGGER.debug(
                    "Authentification Quitoque non confirmée : status=%s "
                    "location=%s is_logged=%s error=%s",
                    status,
                    location,
                    is_logged_value,
                    error_message,
                )

                raise QuitoqueAuthenticationError(
                    error_message
                    or "Identifiant ou mot de passe Quitoque incorrect"
                )

            dashboard_html, dashboard_url = await self._async_get_text(DASHBOARD_URL)
        except QuitoqueAuthenticationError:
            raise
        except ClientResponseError as err:
            raise QuitoqueError(f"Erreur HTTP Quitoque : {err.status}") from err
        except (ClientError, TimeoutError) as err:
            raise QuitoqueError("Impossible de joindre Quitoque") from err

        if self._looks_like_login_page(dashboard_html, dashboard_url):
            raise QuitoqueAuthenticationError(
                "La connexion Quitoque n'a pas été conservée"
            )
        if not self._is_connected_page(dashboard_html):
            raise QuitoqueAuthenticationError("Quitoque ne confirme pas la connexion")

        _LOGGER.debug(
            "Connexion Quitoque confirmée : dashboard=%s cookies=%s",
            dashboard_url,
            sorted(cookie.key for cookie in self._session.cookie_jar),
        )

        self._authenticated = True
        self._emit_auth_event("login_success")
        if auto_reconnect:
            self._emit_auth_event("auto_reconnect")

    async def async_get_recipe_details(
        self,
        recipe: QuitoqueRecipe,
    ) -> QuitoqueRecipeDetails:
        """Fetch and parse a recipe, transparently refreshing an expired session."""
        if not recipe.detail_url:
            raise QuitoqueParseError(
                f"URL détaillée introuvable pour la recette {recipe.name}"
            )

        if not self._authenticated:
            await self.async_login()

        for attempt in range(2):
            headers = self._headers()
            headers.update(
                {
                    "Accept": (
                        "text/html,application/xhtml+xml,"
                        "application/json;q=0.9,*/*;q=0.8"
                    ),
                    "Referer": DASHBOARD_URL,
                }
            )

            try:
                async with self._session.get(
                    recipe.detail_url,
                    headers=headers,
                    allow_redirects=True,
                    timeout=30,
                ) as response:
                    response.raise_for_status()
                    html = await response.text(errors="replace")
                    final_url = str(response.url)
            except ClientResponseError as err:
                raise QuitoqueError(
                    f"Erreur HTTP Quitoque pour la recette : {err.status}"
                ) from err
            except (ClientError, TimeoutError) as err:
                raise QuitoqueError(
                    f"Impossible de récupérer la recette {recipe.name}"
                ) from err

            if self._looks_like_login_page(html, final_url):
                self._authenticated = False
                if attempt == 0:
                    await self._async_auto_reconnect()
                    continue
                raise QuitoqueAuthenticationError(
                    "La session Quitoque a expiré après reconnexion"
                )

            steps = _extract_recipe_steps(html)
            image_url = _extract_recipe_image_url(html, final_url)
            (
                ingredients,
                kitchen_ingredients,
                equipment,
                servings,
            ) = _extract_recipe_structured_data(html)
            if not steps:
                raise QuitoqueParseError(
                    f"Déroulé introuvable pour la recette {recipe.name}"
                )

            _LOGGER.debug(
                "Déroulé Quitoque extrait : recette=%s étapes=%s",
                recipe.name,
                len(steps),
            )
            return QuitoqueRecipeDetails(
                name=recipe.name,
                duration_minutes=(
                    recipe.duration_minutes
                    if recipe.duration_minutes is not None
                    else _extract_recipe_page_duration(html)
                ),
                source_url=recipe.detail_url,
                image_url=image_url,
                steps=steps,
                ingredients=ingredients,
                kitchen_ingredients=kitchen_ingredients,
                equipment=equipment,
                servings=servings,
            )

        raise QuitoqueAuthenticationError(
            "La session Quitoque n'a pas pu être rétablie"
        )

    async def async_get_image_bytes(self, image_url: str) -> bytes:
        """Download a recipe image for PDF generation."""
        try:
            async with self._session.get(
                image_url,
                headers={
                    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
                    "Referer": BASE_URL,
                    "User-Agent": USER_AGENT,
                },
                allow_redirects=True,
                timeout=30,
            ) as response:
                response.raise_for_status()
                return await response.read()
        except ClientResponseError as err:
            raise QuitoqueError(
                f"Erreur HTTP Quitoque pour l'image : {err.status}"
            ) from err
        except (ClientError, TimeoutError) as err:
            raise QuitoqueError(
                "Impossible de récupérer l'image de la recette"
            ) from err

    async def _async_discover_recent_history_orders(
        self,
    ) -> tuple[QuitoqueOrder, ...]:
        """Return ordered boxes belonging to the current and next week."""
        dashboard_html, final_url = await self._async_get_text(DASHBOARD_URL)
        if self._looks_like_login_page(dashboard_html, final_url):
            self._authenticated = False
            raise QuitoqueAuthenticationError("La session Quitoque a expiré")

        pages: list[tuple[str, str]] = [(dashboard_html, final_url)]
        link_parser = _HistoryLinkParser()
        link_parser.feed(dashboard_html)

        seen_urls = {final_url}
        discovered_urls = list(link_parser.urls[:3])
        if not discovered_urls:
            discovered_urls.extend(
                urljoin(BASE_URL, path)
                for path in (
                    "/mes-box-commandees",
                    "/mes-commandes",
                    "/commandes",
                    "/orders",
                    "/compte/commandes",
                )
            )

        for url in discovered_urls:
            if url in seen_urls:
                continue
            seen_urls.add(url)
            try:
                html, page_url = await self._async_get_text(url)
            except QuitoqueError:
                _LOGGER.debug("Route historique Quitoque ignorée : %s", url)
                continue
            if self._looks_like_login_page(html, page_url):
                self._authenticated = False
                raise QuitoqueAuthenticationError("La session Quitoque a expiré")
            probe = _HistoricalOrdersParser()
            probe.feed(html)
            if probe.cards:
                pages.append((html, page_url))
                break

        today = date.today()
        current_monday = today - timedelta(days=today.weekday())
        range_end = current_monday + timedelta(weeks=2)

        cards_by_id: dict[int, _HistoricalOrderCard] = {}
        for html, _ in pages:
            parser = _HistoricalOrdersParser()
            parser.feed(html)
            for card in parser.cards:
                if current_monday <= card.delivery_date < range_end:
                    cards_by_id[card.order_id] = card

        if not cards_by_id:
            _LOGGER.debug("Aucune box Quitoque S0/S+1 détectée dans l'historique")
            return ()

        orders: list[QuitoqueOrder] = []
        for card in sorted(cards_by_id.values(), key=lambda item: item.delivery_date):
            orders.append(await self._async_history_card_to_order(card))

        _LOGGER.debug(
            "Box Quitoque historiques S0/S+1 détectées : %s",
            [f"{order.order_id}:{order.delivery_date.isoformat()}" for order in orders],
        )
        return tuple(orders)

    async def _async_history_card_to_order(
        self,
        card: _HistoricalOrderCard,
    ) -> QuitoqueOrder:
        """Build an order from a history card and its recap when available."""
        recap_html = ""
        try:
            recap_html, final_url = await self._async_get_text(card.details_url)
            if self._looks_like_login_page(recap_html, final_url):
                self._authenticated = False
                raise QuitoqueAuthenticationError("La session Quitoque a expiré")

            try:
                parsed = self._parse_order(recap_html, card.details_url)
            except QuitoqueParseError:
                parsed = None
            if parsed is not None:
                return parsed
        except QuitoqueAuthenticationError:
            raise
        except QuitoqueError:
            _LOGGER.debug(
                "Récapitulatif Quitoque indisponible pour la commande %s",
                card.order_id,
                exc_info=True,
            )

        recipe_names_list = list(card.recipe_names)
        if recap_html:
            for name in re.findall(
                r'<img[^>]+alt=["\']([^"\']+)["\']',
                recap_html,
                re.I,
            ):
                cleaned_name = unescape(name).strip()
                if cleaned_name and cleaned_name not in recipe_names_list:
                    recipe_names_list.append(cleaned_name)
        recipe_names = tuple(recipe_names_list)

        recipes = tuple(
            QuitoqueRecipe(
                item_id=_stable_history_recipe_id(card.order_id, name),
                name=name,
                category="recipe",
                quantity=1,
                duration_minutes=None,
                detail_url=urljoin(BASE_URL, f"/recettes/{_recipe_slug(name)}"),
            )
            for name in recipe_names
        )
        if not recipes:
            raise QuitoqueParseError(
                f"Aucune recette trouvée pour la commande Quitoque {card.order_id}"
            )

        start_hour, end_hour = (
            _extract_delivery_hours(recap_html)
            if recap_html
            else (None, None)
        )
        return QuitoqueOrder(
            order_id=card.order_id,
            delivery_date=card.delivery_date,
            delivery_start_hour=start_hour,
            delivery_end_hour=end_hour,
            recipes_url=card.details_url,
            recipes=recipes,
        )

    async def _async_discover_recipes_urls(self) -> tuple[str, ...]:
        """Return recipe URLs for active planned Quitoque boxes."""
        html, final_url = await self._async_get_text(DASHBOARD_URL)
        if self._looks_like_login_page(html, final_url):
            self._authenticated = False
            raise QuitoqueAuthenticationError("La session Quitoque a expiré")

        active_parser = _ActiveWeeksParser()
        active_parser.feed(html)
        active_weeks = active_parser.active_weeks
        _LOGGER.debug(
            "Semaines Quitoque actives détectées : %s", sorted(active_weeks)
        )

        candidates: dict[str, date] = {}
        for match in _RECIPE_URL_RE.finditer(html):
            start_date = date.fromisoformat(match.group("start"))
            week = start_date.strftime("%Y%m%d")

            if week not in active_weeks:
                _LOGGER.debug(
                    "Box Quitoque ignorée car suspendue : semaine=%s url=%s",
                    week,
                    match.group("url"),
                )
                continue

            url = urljoin(
                BASE_URL, match.group("url").replace("/panier", "/recettes")
            )
            candidates[url] = start_date

        today = date.today()
        future = sorted(
            (
                (url, start_date)
                for url, start_date in candidates.items()
                if start_date >= today
            ),
            key=lambda item: item[1],
        )

        if not future:
            _LOGGER.debug("Aucune box Quitoque active future détectée")
            return ()

        _LOGGER.debug(
            "Box Quitoque actives futures détectées : %s",
            [start_date.isoformat() for _, start_date in future],
        )
        return tuple(url for url, _ in future)

    async def _async_discover_recipes_url(self) -> str | None:
        """Return the recipes URL of the next active Quitoque box."""
        urls = await self._async_discover_recipes_urls()
        return urls[0] if urls else None

    async def _async_get_text(self, url: str) -> tuple[str, str]:
        try:
            async with self._session.get(
                url,
                headers=self._headers(),
                allow_redirects=True,
                timeout=30,
            ) as response:
                response.raise_for_status()
                return await response.text(errors="replace"), str(response.url)
        except ClientResponseError as err:
            raise QuitoqueError(f"Erreur HTTP Quitoque : {err.status}") from err
        except (ClientError, TimeoutError) as err:
            raise QuitoqueError("Impossible de joindre Quitoque") from err

    @staticmethod
    def _headers() -> dict[str, str]:
        return {
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
            "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "User-Agent": USER_AGENT,
        }

    @staticmethod
    def _looks_like_login_page(html: str, final_url: str) -> bool:
        lowered_url = final_url.lower().rstrip("/")
        if lowered_url.endswith("/login") or lowered_url.endswith("/connexion"):
            return True
        lowered = html.lower()
        return (
            'action="/login-check"' in lowered
            and 'name="_password"' in lowered
            and 'name="_username"' in lowered
        )

    @staticmethod
    def _is_connected_page(html: str) -> bool:
        return (
            "user_connection&quot;:&quot;connected&quot;" in html
            or '"user_connection":"connected"' in unescape(html)
            or "href='/compte'" in html
            or 'href="/compte"' in html
        )

    @staticmethod
    def _parse_order(html: str, recipes_url: str) -> QuitoqueOrder:
        parser = _GtmDataParser()
        parser.feed(html)
        if not parser.payload:
            raise QuitoqueParseError("Bloc de données Quitoque introuvable")

        try:
            payload = json.loads(unescape(parser.payload))
            order_id = int(payload["order_id"])
            delivery_date = date.fromisoformat(payload["delivery_day"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as err:
            raise QuitoqueParseError("Données de commande Quitoque invalides") from err

        durations = _extract_recipe_durations(html)
        _LOGGER.debug("Durées Quitoque extraites : %s", durations)

        url_parser = _RecipeUrlParser()
        url_parser.feed(html)
        detail_urls = url_parser.urls
        _LOGGER.debug("URLs détaillées Quitoque extraites : %s", detail_urls)

        recipes: list[QuitoqueRecipe] = []
        for item in payload.get("items", []):
            category = str(item.get("item_category", ""))
            if category not in {"recipe", "kit"}:
                continue
            try:
                recipes.append(
                    QuitoqueRecipe(
                        item_id=int(item["item_id"]),
                        name=str(item["item_name"]),
                        category=category,
                        quantity=int(item.get("quantity", 1)),
                        price_cents=(
                            int(item["price"])
                            if item.get("price") is not None
                            else None
                        ),
                        duration_minutes=durations.get(int(item["item_id"])),
                        detail_url=(
                            detail_urls.get(int(item["item_id"]))
                            or urljoin(
                                BASE_URL,
                                f"/recettes/{_recipe_slug(str(item['item_name']))}",
                            )
                        ),
                    )
                )
            except (KeyError, TypeError, ValueError):
                _LOGGER.debug("Élément Quitoque ignoré car incomplet : %s", item)

        if not recipes:
            raise QuitoqueParseError("Aucune recette sélectionnée n'a été trouvée")

        return QuitoqueOrder(
            order_id=order_id,
            delivery_date=delivery_date,
            delivery_start_hour=_optional_int(
                payload.get("delivery_time_slot_start_at")
            ),
            delivery_end_hour=_optional_int(payload.get("delivery_time_slot_end_at")),
            recipes_url=recipes_url,
            recipes=tuple(recipes),
        )

    @staticmethod
    def _extract_login_error(html: str) -> str | None:
        """Extract the authentication error displayed by Quitoque."""
        patterns = (
            r'class=["\'][^"\']*(?:alert|error|message)[^"\']*["\'][^>]*>\s*(.*?)\s*</',
            r"<li[^>]*>\s*(Session invalide.*?)\s*</li>",
            r"<div[^>]*>\s*(Session invalide.*?)\s*</div>",
            r"<p[^>]*>\s*(Session invalide.*?)\s*</p>",
            r"<li[^>]*>\s*(Identifiant.*?)\s*</li>",
            r"<div[^>]*>\s*(Identifiant.*?)\s*</div>",
        )

        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
            if not match:
                continue

            message = re.sub(r"<[^>]+>", " ", match.group(1))
            message = unescape(message)
            message = re.sub(r"\s+", " ", message).strip()

            if message:
                return message

        return None


def _optional_int(value: object) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
