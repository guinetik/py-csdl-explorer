"""Test full CSDL Explorer app rendering."""
import asyncio
import sys
from pathlib import Path

def log(msg):
    sys.stderr.write(msg + "\n")
    sys.stderr.flush()

from csdl_explore.app import CSDLExplorerApp
from csdl_explore.explorer import CSDLExplorer


async def test():
    metadata_path = Path("metadata.xml")
    if not metadata_path.exists():
        log("metadata.xml not found in current directory, skipping test")
        return

    e = CSDLExplorer.from_file(metadata_path)
    log(f"Loaded {e.entity_count} entities")

    app = CSDLExplorerApp(e)
    async with app.run_test(size=(140, 45)) as pilot:
        # Select first available entity
        entities = e.list_entities()
        if entities:
            app._show_entity(entities[0])
            await pilot.pause()
            await pilot.pause()

            svg = app.export_screenshot()
            log(f"First entity in SVG: {entities[0] in svg}")

            with open("screenshot.svg", "w", encoding="utf-8") as f:
                f.write(svg)
            log("screenshot.svg saved")


asyncio.run(test())
