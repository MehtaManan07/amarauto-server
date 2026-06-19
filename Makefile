APP_MODULE=app.main:app
HOST=127.0.0.1
PORT=8002
ALEMBIC=alembic
ALEMBIC_CONFIG=alembic.ini

# Run FastAPI server (against Turso)
run:
	uvicorn $(APP_MODULE) --host $(HOST) --port $(PORT) --reload

# Run against a local SQLite copy (fast offline dev — no Turso round-trips).
# First sync the copy:  make sync-local   (or python -m scripts.sync_local_db)
run-local:
	USE_LOCAL_DB=1 uvicorn $(APP_MODULE) --host $(HOST) --port $(PORT) --reload

# Pull a fresh local copy of the Turso DB
sync-local:
	python -m scripts.sync_local_db

# Alembic commands
migrate:
	$(ALEMBIC) -c $(ALEMBIC_CONFIG) upgrade head

# Create Alembic revision with a custom message: make makemigration msg="your message"
makemigration:
ifndef msg
	$(error You must provide a message using msg="your message")
endif
	$(ALEMBIC) -c $(ALEMBIC_CONFIG) revision --autogenerate -m "$(msg)"


downgrade:
	$(ALEMBIC) -c $(ALEMBIC_CONFIG) downgrade -1

# Show Alembic current version
dbversion:
	$(ALEMBIC) -c $(ALEMBIC_CONFIG) current

# Clean __pycache__ and .pyc files
clean:
	find . -type d -name '__pycache__' -exec rm -r {} +
	find . -type f -name '*.pyc' -delete