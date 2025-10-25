from sqlalchemy.orm import declarative_base

Base = declarative_base()

# Ensure that all model classes are imported so their mappers are configured.
# We import via importlib to avoid Pylance unused‑import warnings.
import importlib
importlib.import_module("app.db.models")