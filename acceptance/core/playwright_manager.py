"""
Playwright browser lifecycle manager.

Manages browser creation, context/page setup, and cleanup.
Integrates ConsoleMonitor and NetworkMonitor into each new page.
"""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright

from .console_monitor import ConsoleMonitor
from .network_monitor import NetworkMonitor


class PlaywrightManager:
    """
    Async context manager for Playwright browser lifecycle.

    Usage:
        async with PlaywrightManager() as pm:
            page = await pm.new_page()
            await page.goto("http://localhost:3000")
            # ... run acceptance tests ...
            await pm.take_screenshot(page, "final-state")

    Each new page automatically gets console and network monitoring attached.
    """

    def __init__(
        self,
        browser_type: str = "chromium",
        headless: bool = True,
        slow_mo: int = 0,
        viewport_width: int = 1280,
        viewport_height: int = 720,
        screenshot_dir: str = "reports/screenshots",
    ):
        self._browser_type = browser_type
        self._headless = headless
        self._slow_mo = slow_mo
        self._viewport_width = viewport_width
        self._viewport_height = viewport_height
        self._screenshot_dir = Path(screenshot_dir)

        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._pages: list[Page] = []
        self._console_monitors: Dict[int, ConsoleMonitor] = {}
        self._network_monitors: Dict[int, NetworkMonitor] = {}

    async def __aenter__(self) -> PlaywrightManager:
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.stop()

    async def start(self) -> None:
        """Start Playwright and launch browser."""
        self._playwright = await async_playwright().start()

        launch_kwargs: Dict[str, Any] = {
            "headless": self._headless,
        }
        if self._slow_mo > 0:
            launch_kwargs["slow_mo"] = self._slow_mo

        if self._browser_type == "firefox":
            self._browser = await self._playwright.firefox.launch(**launch_kwargs)
        elif self._browser_type == "webkit":
            self._browser = await self._playwright.webkit.launch(**launch_kwargs)
        else:
            self._browser = await self._playwright.chromium.launch(**launch_kwargs)

        self._screenshot_dir.mkdir(parents=True, exist_ok=True)

    async def stop(self) -> None:
        """Close browser and stop Playwright."""
        # Detach monitors
        for page in self._pages:
            pid = id(page)
            if pid in self._console_monitors:
                self._console_monitors[pid].detach(page)
            if pid in self._network_monitors:
                self._network_monitors[pid].detach(page)

        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

        self._browser = None
        self._playwright = None
        self._pages.clear()
        self._console_monitors.clear()
        self._network_monitors.clear()

    async def new_page(self, **context_kwargs) -> Page:
        """
        Create a new browser context and page with monitoring attached.

        Args:
            **context_kwargs: Additional BrowserContext options (e.g., extra_http_headers).

        Returns:
            Playwright Page with console and network monitoring active.
        """
        if not self._browser:
            raise RuntimeError("Browser not started. Use 'async with PlaywrightManager()' or call start() first.")

        context = await self._browser.new_context(
            viewport={"width": self._viewport_width, "height": self._viewport_height},
            **context_kwargs,
        )
        page = await context.new_page()

        # Attach monitors
        console_monitor = ConsoleMonitor()
        console_monitor.attach(page)

        network_monitor = NetworkMonitor()
        network_monitor.attach(page)

        self._console_monitors[id(page)] = console_monitor
        self._network_monitors[id(page)] = network_monitor
        self._pages.append(page)

        return page

    def get_console_monitor(self, page: Page) -> Optional[ConsoleMonitor]:
        """Get the console monitor attached to a page."""
        return self._console_monitors.get(id(page))

    def get_network_monitor(self, page: Page) -> Optional[NetworkMonitor]:
        """Get the network monitor attached to a page."""
        return self._network_monitors.get(id(page))

    async def take_screenshot(self, page: Page, name: str, full_page: bool = False) -> Path:
        """
        Take a screenshot and save to the configured directory.

        Args:
            page: Playwright Page to capture.
            name: Filename (without extension). Timestamp will be prepended.
            full_page: Whether to capture the full scrollable page.

        Returns:
            Path to the saved screenshot file.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
        filename = f"{timestamp}_{safe_name}.png"
        filepath = self._screenshot_dir / filename

        await page.screenshot(path=str(filepath), full_page=full_page)
        return filepath

    async def new_context(self, **kwargs) -> BrowserContext:
        """Create a new browser context without creating a page."""
        if not self._browser:
            raise RuntimeError("Browser not started.")
        return await self._browser.new_context(
            viewport={"width": self._viewport_width, "height": self._viewport_height},
            **kwargs,
        )

    @property
    def pages(self) -> list[Page]:
        return list(self._pages)

    @property
    def is_running(self) -> bool:
        return self._browser is not None
