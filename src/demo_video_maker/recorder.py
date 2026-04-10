"""Browser automation and screenshot capture using Playwright."""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

from playwright.async_api import Page, async_playwright

from demo_video_maker.models import ActionType, Manifest, Scenario, Step, StepResult

logger = logging.getLogger(__name__)


async def _execute_step(page: Page, step: Step, base_url: str) -> None:
    """Execute a single browser action.

    Args:
        page: Playwright page instance.
        step: Step definition to execute.
        base_url: Base URL to prepend for navigation actions.
    """
    match step.action:
        case ActionType.NAVIGATE:
            url = step.url if step.url and step.url.startswith("http") else f"{base_url}{step.url}"
            await page.goto(url, wait_until="networkidle")
        case ActionType.CLICK:
            if step.selector:
                loc = page.locator(step.selector).first
                try:
                    await loc.scroll_into_view_if_needed(timeout=5000)
                except Exception:
                    pass
                try:
                    await loc.click(timeout=10000)
                except Exception:
                    logger.warning("Click failed on %s, using JS click", step.selector)
                    await page.evaluate(
                        "(sel) => { const el = document.querySelector(sel); if (el) el.click(); }",
                        step.selector,
                    )
        case ActionType.TYPE:
            if step.selector and step.text:
                loc = page.locator(step.selector).first
                try:
                    await loc.scroll_into_view_if_needed(timeout=5000)
                except Exception:
                    pass
                await loc.fill(step.text, timeout=10000)
        case ActionType.HOVER:
            if step.selector:
                loc = page.locator(step.selector).first
                try:
                    await loc.scroll_into_view_if_needed(timeout=5000)
                except Exception:
                    pass
                await loc.hover(timeout=10000)
        case ActionType.SCROLL:
            if step.selector:
                await page.evaluate(
                    "(args) => document.querySelector(args.sel).scrollBy(0, args.d)",
                    {"sel": step.selector, "d": step.distance},
                )
            else:
                await page.evaluate("(d) => window.scrollBy(0, d)", step.distance)
        case ActionType.WAIT:
            await asyncio.sleep(step.wait_seconds)
        case ActionType.SCREENSHOT:
            pass  # screenshot is always taken after action

    if step.wait_for:
        await page.wait_for_selector(step.wait_for, timeout=15000)


async def _apply_highlight(page: Page, selector: str) -> None:
    """Add a visual highlight overlay to an element.

    Args:
        page: Playwright page instance.
        selector: CSS selector for the element to highlight.
    """
    await page.evaluate("""(sel) => {
        const el = document.querySelector(sel);
        if (el) {
            el.dataset.origOutline = el.style.outline;
            el.dataset.origOutlineOffset = el.style.outlineOffset;
            el.style.outline = '3px solid #4f86f7';
            el.style.outlineOffset = '4px';
            el.style.transition = 'outline 0.3s ease';
        }
    }""", selector)


async def _remove_highlight(page: Page, selector: str) -> None:
    """Remove the visual highlight overlay from an element.

    Args:
        page: Playwright page instance.
        selector: CSS selector for the highlighted element.
    """
    await page.evaluate("""(sel) => {
        const el = document.querySelector(sel);
        if (el) {
            el.style.outline = el.dataset.origOutline || '';
            el.style.outlineOffset = el.dataset.origOutlineOffset || '';
        }
    }""", selector)


_INJECT_CURSOR_JS = """() => {
    if (document.getElementById('__demo_cursor')) return;
    const cursor = document.createElement('div');
    cursor.id = '__demo_cursor';
    Object.assign(cursor.style, {
        position: 'fixed',
        width: '48px',
        height: '48px',
        borderRadius: '50%',
        background: 'radial-gradient(circle, rgba(239,68,68,0.95) 0%, rgba(239,68,68,0.5) 50%, transparent 70%)',
        border: '3px solid rgba(255,255,255,0.9)',
        boxShadow: '0 0 16px rgba(239,68,68,0.6), 0 4px 8px rgba(0,0,0,0.4)',
        pointerEvents: 'none',
        zIndex: '2147483647',
        transform: 'translate(-50%, -50%)',
        transition: 'left 0.3s ease, top 0.3s ease, transform 0.15s ease',
        display: 'none',
    });
    document.body.appendChild(cursor);
}"""


async def _show_cursor_at(page: Page, x: int, y: int, *, clicked: bool = False) -> None:
    """Position the injected DOM cursor at the given viewport coordinates.

    Args:
        page: Playwright page instance.
        x: Viewport X coordinate.
        y: Viewport Y coordinate.
        clicked: If True, show a click-pulse animation.
    """
    await page.evaluate(_INJECT_CURSOR_JS)
    scale = "scale(1.6)" if clicked else "scale(1)"
    await page.evaluate(f"""() => {{
        const c = document.getElementById('__demo_cursor');
        if (!c) return;
        c.style.display = 'block';
        c.style.left = '{x}px';
        c.style.top = '{y}px';
        c.style.transform = 'translate(-50%, -50%) {scale}';
    }}""")
    if clicked:
        await asyncio.sleep(0.15)
        await page.evaluate("""() => {
            const c = document.getElementById('__demo_cursor');
            if (c) c.style.transform = 'translate(-50%, -50%) scale(1)';
        }""")


async def _hide_cursor(page: Page) -> None:
    """Hide the injected DOM cursor."""
    await page.evaluate("""() => {
        const c = document.getElementById('__demo_cursor');
        if (c) c.style.display = 'none';
    }""")


async def record_scenario(
    scenario: Scenario,
    output_dir: Path,
    *,
    base_url_override: str | None = None,
    headless: bool = True,
    video_clips: bool = False,
) -> Manifest:
    """Record a demo scenario, producing frames (and optionally a session video) and a manifest.

    When video_clips is True, the entire browser session is recorded as a
    single video using Playwright's built-in recording. Step timestamps are
    tracked so the stitcher can overlay narration at the correct offsets.

    Args:
        scenario: Parsed scenario definition.
        output_dir: Directory to write frames and manifest into.
        base_url_override: Override the scenario's base_url.
        headless: Run browser in headless mode.
        video_clips: If True, record the full session as video.

    Returns:
        Manifest linking each step to its frame, optional video, and narration text.
    """
    base_url = base_url_override or scenario.base_url
    frames_dir = output_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    video_dir: Path | None = None
    if video_clips:
        video_dir = output_dir / "video"
        video_dir.mkdir(parents=True, exist_ok=True)

    step_results: list[StepResult] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)

        ctx_kwargs: dict[str, object] = {
            "viewport": {"width": scenario.resolution[0], "height": scenario.resolution[1]},
            "ignore_https_errors": True,
        }
        if video_dir:
            ctx_kwargs["record_video_dir"] = str(video_dir)
            ctx_kwargs["record_video_size"] = {
                "width": scenario.resolution[0],
                "height": scenario.resolution[1],
            }

        context = await browser.new_context(**ctx_kwargs)
        page = await context.new_page()

        # Pre-navigate to avoid blank white frame at video start
        if video_dir and scenario.steps:
            first = scenario.steps[0]
            if first.action == ActionType.NAVIGATE and first.url:
                url = first.url if first.url.startswith("http") else f"{base_url}{first.url}"
                await page.goto(url, wait_until="networkidle")

        session_t0 = time.monotonic()

        for i, step in enumerate(scenario.steps):
            logger.info("Step %d/%d: %s", i + 1, len(scenario.steps), step.action.value)

            step_t0 = time.monotonic() - session_t0
            pause = step.duration_override or scenario.pause_between_steps

            # Cursor positioning
            cursor_selector = step.selector or step.highlight
            cursor_on_target = step.action in {
                ActionType.CLICK, ActionType.HOVER, ActionType.TYPE,
            }

            click_position: tuple[int, int] | None = None
            if cursor_on_target and cursor_selector:
                try:
                    box = await page.locator(cursor_selector).bounding_box(timeout=5000)
                except Exception:
                    box = None
                if box:
                    cx = int(box["x"] + box["width"] / 2)
                    cy = int(box["y"] + box["height"] / 2)
                    if step.action == ActionType.CLICK:
                        click_position = (cx, cy)
                    await _show_cursor_at(page, cx, cy)
                    await asyncio.sleep(0.3)

            await _execute_step(page, step, base_url)

            # Post-action visuals (may fail if action triggered navigation)
            try:
                if click_position:
                    await _show_cursor_at(
                        page, click_position[0], click_position[1], clicked=True,
                    )
                elif step.action in {ActionType.NAVIGATE, ActionType.SCREENSHOT}:
                    await _hide_cursor(page)

                if step.highlight:
                    await _apply_highlight(page, step.highlight)
            except Exception:
                logger.debug("Post-action visuals skipped (page navigated)")

            # Hold for pause duration (visible in video recording)
            await asyncio.sleep(pause)

            # Capture screenshot (always — used for GIF, HTML tutorial, fallback)
            frame_path = frames_dir / f"step_{i:03d}.png"
            await page.screenshot(path=str(frame_path), full_page=False)

            step_duration = time.monotonic() - session_t0 - step_t0

            step_results.append(
                StepResult(
                    index=i,
                    frame_path=str(frame_path),
                    narration=step.narration,
                    duration=step_duration if video_clips else pause,
                    click_position=click_position,
                )
            )

            if step.highlight:
                try:
                    await _remove_highlight(page, step.highlight)
                except Exception:
                    pass

        # Finalize video recording
        session_video_path: str | None = None
        if video_clips:
            video = page.video
            if video:
                session_video_path = str(await video.path())

        await context.close()
        await browser.close()

    # In clip mode, store the session video path on the first step
    # so the stitcher knows to use it
    if session_video_path:
        step_results[0].video_path = session_video_path

    manifest = Manifest(title=scenario.title, steps=step_results)
    manifest.save(output_dir / "manifest.json")
    logger.info("Recorded %d steps to %s", len(step_results), output_dir)
    return manifest
