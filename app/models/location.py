"""
CivicPulse Location Model

Defines the locations table storing structured geospatial information
for civic issue sites and incidents.

Design decisions:
    - Stores explicit latitude and longitude coordinates.
    - Database-level check constraints enforce valid WGS84 geographic bounds:
      latitude between -90 and 90, longitude between -180 and 180.
    - Clean foundation ready for future PostGIS geometry column migrations.
    - Includes municipal addressing attributes (area, city, pincode, landmark).
"""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Float, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.complaint import Complaint


class Location(Base, TimestampMixin):
    """
    Physical geographic location of a reported civic issue.

    Attributes:
        id: Primary UUID identifier for location.
        latitude: Geographic latitude in decimal degrees (-90 to +90).
        longitude: Geographic longitude in decimal degrees (-180 to +180).
        address_line: Street address or nearby building description.
        area_name: Ward, neighbourhood, or administrative sector name.
        city: City or municipal corporation name.
        pincode: Postal code.
        landmark: Notable nearby physical reference point.
    """

    __tablename__ = "locations"
    __table_args__ = (
        CheckConstraint(
            "latitude >= -90.0 AND latitude <= 90.0",
            name="chk_location_latitude_range",
        ),
        CheckConstraint(
            "longitude >= -180.0 AND longitude <= 180.0",
            name="chk_location_longitude_range",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Primary UUID identifier for location record",
    )
    latitude: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Latitude coordinate (-90.0 to 90.0)",
    )
    longitude: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Longitude coordinate (-180.0 to 180.0)",
    )
    address_line: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Street address or physical site description",
    )
    area_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="Locality, ward, or community sector",
    )
    city: Mapped[str] = mapped_column(
        String(100),
        default="Default City",
        server_default="Default City",
        nullable=False,
        index=True,
        comment="Municipality or metropolitan district",
    )
    pincode: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        index=True,
        comment="Postal or ZIP code",
    )
    landmark: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Notable physical point of reference near the site",
    )

    # Relationships
    complaints: Mapped[list["Complaint"]] = relationship(
        back_populates="location",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<Location id={self.id} lat={self.latitude} lon={self.longitude} area='{self.area_name}'>"
