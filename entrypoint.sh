#!/bin/bash
set -e

# Note: Database tables are now created automatically by SQLAlchemy's db.create_all()
# No need for migrations - the models define the schema directly

# Execute the main command
exec "$@"
