"""Authenticated download endpoint for privately stored Quitoque exports."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from aiohttp import web
from homeassistant.components.http import HomeAssistantView

from .pdf_export import PDF_ARCHIVE_RELATIVE_PATH, PDF_DIRECTORY_RELATIVE_PATH


class QuitoqueRecipeDownloadView(HomeAssistantView):
    """Serve private PDF and ZIP exports to authenticated or signed requests."""

    url = "/api/quitoque/recipes/{filename}"
    name = "api:quitoque:recipes"
    requires_auth = True

    def __init__(self, hass):
        self.hass = hass

    async def get(self, request: web.Request, filename: str) -> web.StreamResponse:
        """Return only generated Quitoque PDFs or the generated archive."""
        if filename == "recettes_quitoque.zip":
            path = Path(self.hass.config.path(PDF_ARCHIVE_RELATIVE_PATH))
            content_type = "application/zip"
        elif (
            filename.endswith(".pdf")
            and filename not in {".pdf", "..pdf"}
            and Path(filename).name == filename
        ):
            path = Path(self.hass.config.path(PDF_DIRECTORY_RELATIVE_PATH)) / filename
            content_type = "application/pdf"
        else:
            raise web.HTTPNotFound()

        if not await self.hass.async_add_executor_job(path.is_file):
            raise web.HTTPNotFound()

        response = web.FileResponse(path)
        response.content_type = content_type
        response.headers["Content-Disposition"] = (
            "attachment; filename*=UTF-8''" + quote(filename)
        )
        response.headers["Cache-Control"] = "private, no-store"
        return response
