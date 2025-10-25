# app/db/models/__init__.py

# Import lookup tables and association tables first
from .airline import Airline              # noqa: F401
from .package_airline import PackageAirline  # noqa: F401
from .password_reset_token import PasswordResetToken  # noqa: F401

# Then import the rest of your models
from .user import User                   # noqa: F401
from .agency import Agency               # noqa: F401
from .package import Package             # noqa: F401
from .package_flight import PackageFlight  # noqa: F401
from .package_stay import PackageStay      # noqa: F401
from .package_inclusion import PackageInclusion  # noqa: F401
from .package_price import PackagePrice   # noqa: F401
from .package_itinerary import PackageItinerary  # noqa: F401
from .agency_branch import AgencyBranch   # noqa: F401
from .city import City                    # noqa: F401
from .inquiry import Inquiry              # noqa: F401

__all__ = [
    "Airline",
    "PackageAirline",
    "PasswordResetToken",
    "User",
    "Agency",
    "Package",
    "PackageFlight",
    "PackageStay",
    "PackageInclusion",
    "PackagePrice",
    "PackageItinerary",
    "AgencyBranch",
    "City",
    "Inquiry",
]
