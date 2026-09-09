"""Deployment entrypoint.

The real application is `app/main.py`. This shim exists because hosting
platforms that auto-detect a Python app look for a top-level `main.py` and
run it as `main:app`, ignoring the Dockerfile.

The codebase imports absolutely (`from app.config import ...`), which needs
the PARENT of `app/` on sys.path. So the deployment root must be this
directory (Backend/) — never `Backend/app/`. Deploying the inner directory
copies the package *contents* to the root and every import fails with:

    ModuleNotFoundError: No module named 'app'

Both of these work from here:

    uvicorn main:app          # platform auto-detect
    uvicorn app.main:app      # what the Dockerfile runs
"""

from app.main import app

__all__ = ["app"]
