PGPASSWORD=agent psql -h localhost -U agent -d polyagent -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public; GRANT ALL ON SCHEMA public TO agent; GRANT ALL ON SCHEMA public TO public;"

find ./agent/tools/custom -type f -delete
touch ./agent/tools/custom/__init__.py

uv run alembic upgrade head


fastapi run
