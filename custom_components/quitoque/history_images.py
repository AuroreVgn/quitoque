"""Extract recipe images from Quitoque ordered-box history."""

from __future__ import annotations

from html.parser import HTMLParser
from urllib.parse import urljoin
import re
import unicodedata

from .const import BASE_URL, DASHBOARD_URL


def _norm(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold().replace("’", "'"))
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


class _HistoryImageParser(HTMLParser):
    """Collect recipe-name/image pairs from ordered-box cards and recaps."""

    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.images: dict[str, str] = {}
        self.product_urls: dict[str, str] = {}
        self._active_href: str | None = None

    def handle_starttag(self, tag: str, attrs) -> None:
        attributes = dict(attrs)

        if tag == "a":
            href = attributes.get("href") or ""
            self._active_href = href or None
            return

        if tag != "img":
            return

        name = (attributes.get("alt") or "").strip()
        if not name:
            return

        src = (
            attributes.get("src")
            or attributes.get("data-src")
            or attributes.get("data-lazy-src")
            or attributes.get("data-original")
        )
        if not src:
            # srcset is often used by responsive Quitoque cards.
            srcset = attributes.get("srcset") or attributes.get("data-srcset")
            if srcset:
                first = srcset.split(",")[0].strip().split(" ")[0]
                src = first or None

        key = _norm(name)

        if src and not str(src).startswith("data:"):
            self.images[key] = urljoin(self.base_url, str(src))

        if self._active_href:
            href = str(self._active_href)
            if "/products/" in href or "/recettes/" in href:
                self.product_urls[key] = urljoin(self.base_url, href)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a":
            self._active_href = None


async def async_history_recipe_metadata(client, orders) -> dict[tuple[int, int], dict]:
    """Return image and exact product/detail URLs from account history pages."""
    names_by_norm: dict[str, list[tuple[int, int]]] = {}
    for order in orders:
        for recipe in order.recipes:
            names_by_norm.setdefault(_norm(recipe.name), []).append(
                (order.order_id, recipe.item_id)
            )

    if not names_by_norm:
        return {}

    pages: list[tuple[str, str]] = []

    # Dashboard already contains part of the history for many accounts.
    try:
        html, url = await client._async_get_text(DASHBOARD_URL)
        pages.append((html, url))
    except Exception:
        pass

    # Probe the same known history routes used by api.py.
    for path in (
        "/mes-box-commandees",
        "/mes-commandes",
        "/commandes",
        "/orders",
        "/compte/commandes",
    ):
        try:
            html, url = await client._async_get_text(urljoin(BASE_URL, path))
        except Exception:
            continue
        pages.append((html, url))

    # Also inspect each order recap. Those pages often contain the exact images
    # even when the public recipe has since changed/vanished.
    for order in orders:
        if not order.recipes_url:
            continue
        try:
            html, url = await client._async_get_text(order.recipes_url)
        except Exception:
            continue
        pages.append((html, url))

    found: dict[tuple[int, int], dict] = {}

    for html, page_url in pages:
        parser = _HistoryImageParser(page_url)
        parser.feed(html)
        for norm_name, image_url in parser.images.items():
            keys = names_by_norm.get(norm_name)
            if not keys:
                # tolerate extra visible labels around an exact recipe name
                keys = []
                for target, target_keys in names_by_norm.items():
                    if len(target) >= 12 and (
                        target in norm_name or norm_name in target
                    ):
                        keys.extend(target_keys)
            for key in keys or []:
                found.setdefault(key, {})["image_url"] = image_url

        for norm_name, detail_url in parser.product_urls.items():
            keys = names_by_norm.get(norm_name)
            if not keys:
                keys = []
                for target, target_keys in names_by_norm.items():
                    if len(target) >= 12 and (
                        target in norm_name or norm_name in target
                    ):
                        keys.extend(target_keys)
            for key in keys or []:
                found.setdefault(key, {})["detail_url"] = detail_url

    return found


async def async_history_recipe_images(client, orders) -> dict[tuple[int, int], str]:
    """Backward-compatible image-only view."""
    metadata = await async_history_recipe_metadata(client, orders)
    return {
        key: value["image_url"]
        for key, value in metadata.items()
        if value.get("image_url")
    }
