"""Browser automation and screenshot capture using Playwright."""

from __future__ import annotations

import asyncio
import logging
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
                await page.click(step.selector)
        case ActionType.TYPE:
            if step.selector and step.text:
                await page.fill(step.selector, step.text)
        case ActionType.HOVER:
            if step.selector:
                await page.hover(step.selector)
        case ActionType.SCROLL:
            if step.selector:
                await page.evaluate(
                    f"document.querySelector('{step.selector}')"
                    f".scrollBy(0, {step.distance})"
                )
            else:
                await page.evaluate(f"window.scrollBy(0, {step.distance})")
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
    await page.evaluate(f"""(() => {{
        const el = document.querySelector('{selector}');
        if (el) {{
            el.dataset.origOutline = el.style.outline;
            el.dataset.origOutlineOffset = el.style.outlineOffset;
            el.style.outline = '3px solid #4f86f7';
            el.style.outlineOffset = '4px';
            el.style.transition = 'outline 0.3s ease';
        }}
    }})()""")


async def _remove_highlight(page: Page, selector: str) -> None:
    """Remove the visual highlight overlay from an element.

    Args:
        page: Playwright page instance.
        selector: CSS selector for the highlighted element.
    """
    await page.evaluate(f"""(() => {{
        const el = document.querySelector('{selector}');
        if (el) {{
            el.style.outline = el.dataset.origOutline || '';
            el.style.outlineOffset = el.dataset.origOutlineOffset || '';
        }}
    }})()""")


async def record_scenario(
    scenario: Scenario,
    output_dir: Path,
    *,
    base_url_override: str | None = None,
    headless: bool = True,
) -> Manifest:
    """Record a demo scenario, producing frames and a manifest.

    Args:
        scenario: Parsed scenario definition.
        output_dir: Directory to write frames and manifest into.
        base_url_override: Override the scenario's base_url.
        headless: Run browser in headless mode.

    Returns:
        Manifest linking each step to its frame and narration text.
    """
    base_url = base_url_override or scenario.base_url
    frames_dir = output_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    step_results: list[StepResult] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(
            viewport={"width": scenario.resolution[0], "height": scenario.resolution[1]},
        )
        page = await context.new_page()

        for i, step in enumerate(scenario.steps):
            logger.info("Step %d/%d: %s", i + 1, len(scenario.steps), step.action.value)

            await _execute_step(page, step, base_url)

            # Capture click position for cursor overlay
            click_position: tuple[int, int] | None = None
            if step.action == ActionType.CLICK and step.selector:
                box = await page.locator(step.selector).bounding_box()
                if box:
                    click_position = (
                        int(box["x"] + box["width"] / 2),
                        int(box["y"] + box["height"] / 2),
                    )

            if step.highlight:
                await _apply_highlight(page, step.highlight)

            # Brief pause for rendering/animations
            await asyncio.sleep(0.5)

            frame_path = frames_dir / f"step_{i:03d}.png"
            await page.screenshot(path=str(frame_path), full_page=False)

            step_results.append(
                StepResult(
                    index=i,
                    frame_path=str(frame_path),
                    narration=step.narration,
                    duration=step.duration_override or scenario.pause_between_steps,
                    click_position=click_position,
                )
            )

            if step.highlight:
                await _remove_highlight(page, step.highlight)

        await context.close()
        await browser.close()

    manifest = Manifest(title=scenario.title, steps=step_results)
    manifest.save(output_dir / "manifest.json")
    logger.info("Recorded %d steps to %s", len(step_results), output_dir)
    return manifest
