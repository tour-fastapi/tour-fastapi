
from sqlalchemy.orm import declarative_base
Base = declarative_base()

# example (your file may already import others)
from app.db.models.agency import Agency
from app.db.models.agency_detail import AgencyDetail
