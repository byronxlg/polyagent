#!/bin/bash
# Reset the database to a clean state and start the API server

PGPASSWORD=agent psql -h localhost -U agent -d polyagent -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public; GRANT ALL ON SCHEMA public TO agent; GRANT ALL ON SCHEMA public TO public;"

uv run alembic upgrade head

uv run fastapi dev src/api.py
