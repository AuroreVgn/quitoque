"""Lightweight recipe metadata extraction for the Quitoque Lovelace card."""

from __future__ import annotations

import json
import re
from html import unescape
from urllib.parse import urljoin, quote_plus
from html.parser import HTMLParser

from .api import (
    QuitoqueAuthenticationError,
    QuitoqueClient,
    _extract_recipe_image_url,
)
from .models import QuitoqueRecipe


def _clean(value: object) -> str:
    """Return compact visible text."""
    return re.sub(r"\s+", " ", unescape(str(value))).strip()


def _normalise_name(value: str) -> str:
    """Normalise a recipe title for loose JSON-LD matching."""
    value = unescape(value).casefold()
    value = value.replace("’", "'")
    return re.sub(r"[^a-z0-9àâäéèêëîïôöùûüç]+", " ", value).strip()



class _RecipeCatalogueParser(HTMLParser):
    """Extract public Quitoque catalogue recipe cards."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._href: str | None = None
        self._parts: list[str] = []
        self._image_url: str | None = None
        self.cards: list[dict[str, str | None]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)

        if tag == "a":
            href = attributes.get("href") or ""
            if href.startswith("/recettes/") and href.count("/") >= 2:
                self._href = href
                self._parts = []
                self._image_url = None

                for key in ("title", "aria-label"):
                    value = attributes.get(key)
                    if value:
                        self._parts.append(value)
            return

        if tag == "img" and self._href is not None:
            alt = attributes.get("alt")
            if alt:
                self._parts.append(alt)

            src = (
                attributes.get("src")
                or attributes.get("data-src")
                or attributes.get("data-lazy-src")
            )
            if src and self._image_url is None:
                self._image_url = src

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            value = data.strip()
            if value:
                self._parts.append(value)

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or self._href is None:
            return

        self.cards.append(
            {
                "text": _clean(" ".join(self._parts)),
                "href": self._href,
                "image_url": self._image_url,
            }
        )
        self._href = None
        self._parts = []
        self._image_url = None


def _catalogue_card_duration(text: str) -> int | None:
    """Extract the total duration displayed on a Quitoque catalogue card."""
    # Quitoque catalogue cards display the total time before the title,
    # e.g. "35 min ... Bowl d'aubergine ...".
    match = re.search(
        r"\b(?P<duration>\d+\s*h(?:\s*\d{1,2})?|\d+\s*(?:min|minutes?))\b",
        text,
        re.IGNORECASE,
    )
    return _iso_duration_minutes(match.group("duration")) if match else None


def _catalogue_total_near_recipe(html: str, recipe_name: str) -> int | None:
    """Read the duration immediately preceding a recipe title in catalogue text.

    Quitoque renders the duration outside the recipe <a>, therefore it cannot
    be extracted from the anchor contents alone.
    """
    visible = _visible_text(html)
    wanted = _clean(recipe_name)

    # Exact visible title first.
    positions: list[int] = []
    start = 0
    lower_visible = visible.casefold()
    lower_wanted = wanted.casefold()
    while lower_wanted:
        pos = lower_visible.find(lower_wanted, start)
        if pos < 0:
            break
        positions.append(pos)
        start = pos + len(lower_wanted)

    for pos in positions:
        before = visible[max(0, pos - 180):pos]
        matches = list(
            re.finditer(
                r"\b(\d+\s*h(?:\s*\d{1,2})?|\d+\s*(?:min|minutes?))\b",
                before,
                re.IGNORECASE,
            )
        )
        if matches:
            # Nearest duration to the title is the card's total time.
            return _iso_duration_minutes(matches[-1].group(1))

    return None


async def async_resolve_recipe_catalogue_metadata(
    client: QuitoqueClient,
    recipe_names: list[str],
) -> dict[str, dict]:
    """Resolve catalogue URL, total duration and image for each recipe.

    The catalogue card itself is useful even when the public recipe detail URL
    cannot be matched perfectly. This makes total time and image independent
    from the historical/product detail-page parser.
    """
    resolved: dict[str, dict] = {}

    for recipe_name in dict.fromkeys(recipe_names):
        target = _normalise_name(recipe_name)
        if not target:
            continue

        search_url = (
            "https://www.quitoque.fr/recettes?query="
            + quote_plus(recipe_name)
        )

        try:
            html, final_url = await client._async_get_text(search_url)
        except Exception:
            continue

        parser = _RecipeCatalogueParser()
        parser.feed(html)

        best: dict | None = None
        best_score = 0

        for card in parser.cards:
            text = str(card.get("text") or "")
            norm_visible = _normalise_name(text)
            if not norm_visible:
                continue

            # Exact titles are often surrounded by duration/badge text, so
            # complete-title containment is the main signal.
            if norm_visible == target:
                score = 100
            elif target in norm_visible:
                score = 95
            else:
                # Last fallback: compare the requested title with text after
                # stripping common catalogue badge words/durations.
                stripped = re.sub(
                    r"\b\d+\s*(?:h|min|minutes?)\b",
                    " ",
                    norm_visible,
                    flags=re.IGNORECASE,
                )
                for noise in (
                    "victime de son succes",
                    "ce produit revient tres vite",
                    "option bio",
                    "express",
                    "vegetarien",
                    "proteine",
                    "riche en legumes",
                    "faible en calories",
                    "valeur sure",
                    "decouverte",
                    "kids friendly",
                ):
                    stripped = stripped.replace(noise, " ")
                stripped = re.sub(r"\s+", " ", stripped).strip()

                if target == stripped:
                    score = 90
                elif target in stripped:
                    score = 85
                else:
                    continue

            if score <= best_score:
                continue

            href = str(card.get("href") or "")
            image = card.get("image_url")
            best = {
                "detail_url": urljoin(final_url, href) if href else None,
                "total_duration_minutes": _catalogue_card_duration(text),
                "image_url": (
                    urljoin(final_url, str(image))
                    if image
                    else None
                ),
            }
            best_score = score

        page_total = _catalogue_total_near_recipe(html, recipe_name)

        if best:
            if page_total is not None:
                best["total_duration_minutes"] = page_total
            resolved[recipe_name] = best
        elif page_total is not None:
            # Even when no public detail URL can be resolved, the search page
            # itself is a valid source for the displayed total duration.
            resolved[recipe_name] = {
                "detail_url": None,
                "total_duration_minutes": page_total,
                "image_url": None,
            }

    return resolved


async def async_resolve_recipe_catalogue_urls(
    client: QuitoqueClient,
    recipe_names: list[str],
) -> dict[str, str]:
    """Backward-compatible URL-only view of catalogue metadata."""
    metadata = await async_resolve_recipe_catalogue_metadata(
        client,
        recipe_names,
    )
    return {
        name: values["detail_url"]
        for name, values in metadata.items()
        if values.get("detail_url")
    }




def _iso_duration_minutes(value: object) -> int | None:
    """Convert ISO-8601 or human-readable durations to minutes."""
    if value in (None, ""):
        return None

    text = _clean(value)

    iso = re.fullmatch(
        r"P(?:(?P<days>\d+)D)?T"
        r"(?:(?P<hours>\d+)H)?"
        r"(?:(?P<minutes>\d+)M)?",
        text,
        re.IGNORECASE,
    )
    if iso:
        return (
            int(iso.group("days") or 0) * 1440
            + int(iso.group("hours") or 0) * 60
            + int(iso.group("minutes") or 0)
        )

    hour = re.search(
        r"(?P<hours>\d+)\s*h(?:eure(?:s)?)?"
        r"(?:\s*(?P<minutes>\d{1,2}))?",
        text,
        re.IGNORECASE,
    )
    if hour:
        return int(hour.group("hours")) * 60 + int(hour.group("minutes") or 0)

    minute = re.search(
        r"(?P<minutes>\d+)\s*(?:min|minute(?:s)?)",
        text,
        re.IGNORECASE,
    )
    if minute:
        return int(minute.group("minutes"))

    return None


def _json_ld_recipes(html: str) -> list[dict]:
    """Return Recipe objects found in JSON-LD blocks."""
    results: list[dict] = []

    def walk(value: object) -> None:
        if isinstance(value, dict):
            raw_type = value.get("@type")
            types = raw_type if isinstance(raw_type, list) else [raw_type]
            if any(str(item).casefold() == "recipe" for item in types if item):
                results.append(value)
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    for raw in re.findall(
        r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
        html,
        re.IGNORECASE | re.DOTALL,
    ):
        try:
            walk(json.loads(unescape(raw).strip()))
        except (json.JSONDecodeError, TypeError):
            continue

    return results


class _H1Parser(HTMLParser):
    """Extract the first visible H1."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._inside = False
        self._parts: list[str] = []
        self.value: str | None = None

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag == "h1" and self.value is None:
            self._inside = True
            self._parts = []

    def handle_data(self, data: str) -> None:
        if self._inside:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "h1" and self._inside:
            value = _clean(" ".join(self._parts))
            if value:
                self.value = value
            self._inside = False


def _recipe_page_matches(html: str, recipe_name: str) -> bool:
    """Verify that fetched public page really is the requested recipe."""
    wanted = _normalise_name(recipe_name)
    if not wanted:
        return False

    # Prefer JSON-LD Recipe names when present.
    recipes = _json_ld_recipes(html)
    for recipe in recipes:
        actual = _normalise_name(str(recipe.get("name") or ""))
        if actual and (
            actual == wanted
            or actual in wanted
            or wanted in actual
        ):
            return True

    # Some Quitoque pages do not expose usable JSON-LD. H1 is the next most
    # trustworthy visible identifier.
    parser = _H1Parser()
    parser.feed(html)
    if parser.value:
        actual = _normalise_name(parser.value)
        if actual and (
            actual == wanted
            or actual in wanted
            or wanted in actual
        ):
            return True

    return False


def _best_recipe_json_ld(html: str, recipe_name: str) -> dict | None:
    """Choose the JSON-LD Recipe object matching the requested recipe."""
    recipes = _json_ld_recipes(html)
    if not recipes:
        return None

    wanted = _normalise_name(recipe_name)
    if wanted:
        for recipe in recipes:
            name = _normalise_name(str(recipe.get("name") or ""))
            if not name:
                continue
            if name == wanted or name in wanted or wanted in name:
                return recipe

    # A public Quitoque recipe page normally contains one Recipe object.
    return recipes[0] if len(recipes) == 1 else None


def _servings_from_box_text(html: str) -> str | None:
    """Extract portions from Quitoque's visible 'Dans votre box' section.

    This is more reliable than recipeYield for account/order recipes because
    the page can expose generic structured-data yields that do not correspond
    to the customer's selected box size.
    """
    visible = _visible_text(html)

    patterns = (
        r"dans votre box.{0,120}?\b(?P<count>[1-9]|1[0-2])\s*personnes?\b",
        r"\b(?P<count>[1-9]|1[0-2])\s*personnes?\b.{0,120}?dans votre box",
    )
    for pattern in patterns:
        match = re.search(pattern, visible, re.IGNORECASE)
        if match:
            count = int(match.group("count"))
            return f"{count} personne" if count == 1 else f"{count} personnes"
    return None


def _servings_from_recipe(recipe: dict | None) -> str | None:
    """Conservative structured-data fallback for servings."""
    if not recipe:
        return None

    raw = recipe.get("recipeYield")
    if isinstance(raw, list):
        raw = raw[0] if raw else None
    if isinstance(raw, dict):
        raw = raw.get("value") or raw.get("name") or raw.get("label")
    if raw in (None, ""):
        return None

    text = _clean(raw)
    match = re.fullmatch(r"\s*(\d{1,2})\s*(?:personnes?|portions?)?\s*", text, re.I)
    if not match:
        return None

    count = int(match.group(1))
    if not 1 <= count <= 12:
        return None
    return f"{count} personne" if count == 1 else f"{count} personnes"


def _duration_near_label(text: str, labels: tuple[str, ...]) -> int | None:
    """Extract a duration tightly associated with one visible label."""
    duration = r"(?P<duration>\d+\s*h(?:\s*\d{1,2})?|\d+\s*(?:min|minutes?))"
    label = "|".join(re.escape(item) for item in labels)

    patterns = (
        rf"(?:{label})\s*[:\-–—]?\s*{duration}",
        rf"{duration}\s*(?:{label})",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            parsed = _iso_duration_minutes(match.group("duration"))
            if parsed is not None:
                return parsed
    return None


def _visible_text(html: str) -> str:
    """Build compact text without scripts/styles."""
    visible = re.sub(
        r"<(script|style|noscript)\b[^>]*>.*?</\1>",
        " ",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    visible = re.sub(r"<[^>]+>", " ", visible)
    return _clean(visible)


def _extract_times(
    html: str,
    recipe_json: dict | None,
) -> tuple[int | None, int | None]:
    """Return (total duration, kitchen duration)."""
    total: int | None = None
    kitchen: int | None = None

    if recipe_json:
        total = _iso_duration_minutes(recipe_json.get("totalTime"))

        # prepTime is the best standards-based equivalent of Quitoque's
        # "En cuisine". Use cookTime only as a fallback.
        kitchen = _iso_duration_minutes(recipe_json.get("prepTime"))
        if kitchen is None:
            kitchen = _iso_duration_minutes(recipe_json.get("cookTime"))

    text = _visible_text(html)

    if total is None:
        total = _duration_near_label(
            text,
            (
                "temps total",
                "durée totale",
                "duree totale",
                "temps de préparation total",
            ),
        )

    if kitchen is None:
        kitchen = _duration_near_label(
            text,
            (
                "en cuisine",
                "temps en cuisine",
                "préparation",
                "preparation",
            ),
        )

    return total, kitchen


def _image_from_recipe(
    recipe_json: dict | None,
    html: str,
    final_url: str,
) -> str | None:
    """Return the selected recipe image URL."""
    if recipe_json:
        image = recipe_json.get("image")
        if isinstance(image, list):
            image = image[0] if image else None
        if isinstance(image, dict):
            image = image.get("url") or image.get("contentUrl")
        if isinstance(image, str) and image.strip():
            return urljoin(final_url, image.strip())

    return _extract_recipe_image_url(html, final_url)


def _public_recipe_urls_from_product_url(value: str | None) -> tuple[str, ...]:
    """Derive public recipe URLs from an exact Quitoque /products URL.

    Quitoque currently serves some recipe pages from www.quitoque.fr and some
    historical/current variants more reliably from backstage.quitoque.fr.
    """
    if not value or "/products/" not in value:
        return ()

    path = value.split("/products/", 1)[1].split("?", 1)[0].strip("/")
    # Product slugs end in a numeric internal product id.
    path = re.sub(r"-\d+$", "", path)
    if not path:
        return ()

    return (
        f"https://www.quitoque.fr/recettes/{path}",
        f"https://backstage.quitoque.fr/recettes/{path}",
    )


async def _async_total_from_derived_public_url(
    client: QuitoqueClient,
    recipe: QuitoqueRecipe,
    product_url: str | None,
) -> tuple[int | None, str | None]:
    """Fetch total time/image from public recipe variants inferred from product URL."""
    urls = _public_recipe_urls_from_product_url(product_url)
    if not urls:
        return None, None

    best_image: str | None = None

    for public_url in urls:
        try:
            html, final_url = await client._async_get_text(public_url)
        except Exception:
            continue

        if not _recipe_page_matches(html, recipe.name):
            continue

        recipe_json = _best_recipe_json_ld(html, recipe.name)
        total, _ = _extract_times(html, recipe_json)
        image = _image_from_recipe(recipe_json, html, final_url)
        if image and not best_image:
            best_image = image

        if total is not None:
            return total, image or best_image

    return None, best_image


async def async_get_recipe_card_metadata(
    client: QuitoqueClient,
    recipe: QuitoqueRecipe,
    *,
    detail_url: str | None = None,
    product_url: str | None = None,
) -> dict:
    """Fetch only metadata required by the Lovelace card.

    Unlike async_get_recipe_details(), this does NOT require cooking steps.
    Therefore a change in Quitoque's step markup cannot hide an otherwise
    valid image/duration/serving count from the dashboard card.
    """
    recipe_url = product_url or detail_url or recipe.detail_url

    if not recipe_url:
        derived_total, derived_image = await _async_total_from_derived_public_url(
            client,
            recipe,
            product_url,
        )
        return {
            "name": recipe.name,
            "total_duration_minutes": derived_total,
            "kitchen_duration_minutes": recipe.duration_minutes,
            "servings": None,
            "image_url": derived_image or recipe.image_url,
        }

    if not client._authenticated:
        await client.async_login()

    for attempt in range(2):
        html, final_url = await client._async_get_text(recipe_url)

        if client._looks_like_login_page(html, final_url):
            client._authenticated = False
            if attempt == 0:
                await client._async_auto_reconnect()
                continue
            raise QuitoqueAuthenticationError(
                "La session Quitoque a expiré après reconnexion"
            )

        if not _recipe_page_matches(html, recipe.name):
            return {
                "name": recipe.name,
                "total_duration_minutes": None,
                "kitchen_duration_minutes": None,
                "servings": None,
                "image_url": None,
            }

        recipe_json = _best_recipe_json_ld(html, recipe.name)

        # Never accept a different recipe merely because the page contains a
        # single JSON-LD Recipe object.
        page_name = ""
        if recipe_json:
            page_name = str(recipe_json.get("name") or "")
        if page_name:
            wanted_name = _normalise_name(recipe.name)
            actual_name = _normalise_name(page_name)
            if wanted_name and actual_name and not (
                wanted_name == actual_name
                or wanted_name in actual_name
                or actual_name in wanted_name
            ):
                recipe_json = None

        total, kitchen = _extract_times(html, recipe_json)

        # The old planning-card duration is retained only as a fallback for
        # kitchen time because the historical parser cannot prove it is total.
        if kitchen is None:
            kitchen = recipe.duration_minutes

        image_url = (
            _image_from_recipe(recipe_json, html, final_url)
            or recipe.image_url
        )

        if total is None:
            derived_total, derived_image = await _async_total_from_derived_public_url(
                client,
                recipe,
                product_url or final_url,
            )
            if derived_total is not None:
                total = derived_total
            if not image_url and derived_image:
                image_url = derived_image

        # If the caller supplied a separate catalogue/public recipe URL, use it
        # as a last source for total time. This is particularly useful for
        # recipes whose product slug and public recipe slug differ slightly.
        if total is None and detail_url and detail_url != recipe_url:
            try:
                public_html, public_final_url = await client._async_get_text(detail_url)
            except Exception:
                public_html = ""
                public_final_url = detail_url

            if public_html and _recipe_page_matches(public_html, recipe.name):
                public_json = _best_recipe_json_ld(public_html, recipe.name)
                public_total, _ = _extract_times(public_html, public_json)
                if public_total is not None:
                    total = public_total
                if not image_url:
                    image_url = _image_from_recipe(
                        public_json,
                        public_html,
                        public_final_url,
                    )

        return {
            "name": recipe.name,
            "total_duration_minutes": total,
            "kitchen_duration_minutes": kitchen,
            "servings": (
                _servings_from_box_text(html)
                or _servings_from_recipe(recipe_json)
            ),
            "image_url": image_url,
        }

    raise QuitoqueAuthenticationError(
        "La session Quitoque n'a pas pu être rétablie"
    )
