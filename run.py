"""Entry point: start the local server and open the dashboard."""

from __future__ import annotations

import sys
import threading
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _open_dashboard(url: str) -> None:
    time.sleep(1.5)
    webbrowser.open(url)


def main() -> None:
    import uvicorn

    from backend.config.settings import get_settings

    settings = get_settings()
    dashboard_url = f"http://{settings.host}:{settings.port}/dashboard"

    threading.Thread(
        target=_open_dashboard,
        args=(dashboard_url,),
        daemon=True,
    ).start()

    uvicorn.run(
        "backend.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
