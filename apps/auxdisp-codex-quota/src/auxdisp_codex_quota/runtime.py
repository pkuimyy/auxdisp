"""Independent API cadence, account rotation, and minute-boundary rendering."""

from datetime import datetime
import logging
import time

from .model import AccountStore, PageController
from .render import make_page


LOG = logging.getLogger(__name__)


class Runtime:
    def __init__(self, settings, collector, renderer, output):
        self.settings = settings
        self.collector = collector
        self.renderer = renderer
        self.output = output
        self.store = AccountStore()
        self.pages = PageController(settings.rotation_seconds)
        self.poll_at = 0.0
        self.last_page = None
        self.rendered_frames = 0

    def step(self, now: float, wall: datetime):
        result = self.collector.take()
        if result:
            if result.error is not None:
                self.store.failure(result.error)
                LOG.warning("Collection failed: %s", result.error)
            else:
                self.store.success(result.accounts, result.at)
                LOG.info("Collection complete: %d accounts", len(result.accounts))
        if now >= self.poll_at:
            if self.collector.request():
                self.poll_at = now + self.settings.refresh_seconds
                LOG.info("Read-only collection started")
        self.pages.update(self.store.snapshot.accounts, now)
        self.pages.tick(now)
        page = make_page(self.store.snapshot, self.pages.current, wall, self.settings)
        if page != self.last_page:
            if self.last_page is None or page.key != self.last_page.key:
                LOG.info("Display page %d/%d", page.index, page.total)
            image = self.renderer.render(page)
            self.output.submit(image, page)
            self.last_page = page
            self.rendered_frames += 1

    def run(self, duration=None):
        started = time.monotonic()
        try:
            while duration is None or time.monotonic() - started < duration:
                self.step(time.monotonic(), datetime.now().astimezone())
                time.sleep(0.1)
        finally:
            try:
                self.collector.close()
            finally:
                self.output.close()
