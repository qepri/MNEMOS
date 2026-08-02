#!/bin/bash
set -e

# Schema is owned by Alembic. Only the `app` service sets RUN_MIGRATIONS=true;
# the worker and mcp services must not, or concurrent starts race on the same
# schema. Default when unset is "do not run".
#
# A failed upgrade is fatal by design (set -e above): starting the app against
# a schema that does not match the code is worse than not starting at all.
if [ "$RUN_MIGRATIONS" = "true" ]; then
    echo "[entrypoint] Applying database migrations..."
    flask db upgrade
    echo "[entrypoint] Migrations up to date."
fi

# No package installation happens here. yt-dlp is pinned in requirements.txt
# and updated by rebuilding the image, so container start needs no network.
exec "$@"
