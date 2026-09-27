"""Entrypoint: launch the FastAPI lab with uvicorn."""

import uvicorn

from app.config import get_settings


def main() -> None:
    # Auto-reload is a local-dev convenience, off by default: the app code is COPYed into
    # the image, so in the container a reloader could never see a change and just costs a
    # second process and a slower shutdown. Set APP_RELOAD=1 when running from a checkout.
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.app_reload,
    )


if __name__ == "__main__":
    main()
