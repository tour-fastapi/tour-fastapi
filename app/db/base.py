from app.db.mixins import Base   # ✅ import Base from mixins

# Import all models so Alembic can detect them
from app.db.models.user import User
from app.db.models.agency import Agency
from app.db.models.agency_branch import AgencyBranch
from app.db.models.agency_testimonial import AgencyTestimonial
from app.db.models.city import City
from app.db.models.hotel import Hotel
from app.db.models.inquiry import Inquiry
from app.db.models.package import Package
from app.db.models.package_price import PackagePrice
from app.db.models.package_inclusion import PackageInclusion
from app.db.models.package_itinerary import PackageItinerary
from app.db.models.package_flight import PackageFlight
from app.db.models.package_stay import PackageStay
