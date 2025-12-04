import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, JSON, Integer
from sqlalchemy.dialects.postgresql import UUID
from app.db.database import Base


class BidSynopsisRequirement(Base):
    """
    Stores edited requirement data for bid synopsis.
    Allows users to customize requirement text for each tender.
    """
    __tablename__ = 'bid_synopsis_requirements'

    # Primary Keys
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tender_id = Column(String, nullable=False, index=True)  # tender_ref_number
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True, index=True)

    # Requirement Index (position in the requirements array)
    requirement_index = Column(Integer, nullable=False)

    # Original and edited values
    original_requirement = Column(Text, nullable=True)  # Original requirement text
    edited_requirement = Column(Text, nullable=False)   # User-edited requirement text

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                       onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    def to_dict(self):
        """Convert SQLAlchemy model to dictionary for API responses."""
        return {
            'id': str(self.id),
            'tender_id': self.tender_id,
            'user_id': str(self.user_id) if self.user_id else None,
            'requirement_index': self.requirement_index,
            'original_requirement': self.original_requirement,
            'edited_requirement': self.edited_requirement,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class BidSynopsisCeigallData(Base):
    """
    Stores CEIGALL company data for bid synopsis.
    Allows users to enter company-specific values for each requirement.
    """
    __tablename__ = 'bid_synopsis_ceigall_data'

    # Primary Keys
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tender_id = Column(String, nullable=False, index=True)  # tender_ref_number
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True, index=True)

    # Data Index (position in the requirements array)
    data_index = Column(Integer, nullable=False)

    # Ceigall value
    ceigall_value = Column(Text, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                       onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    def to_dict(self):
        """Convert SQLAlchemy model to dictionary for API responses."""
        return {
            'id': str(self.id),
            'tender_id': self.tender_id,
            'user_id': str(self.user_id) if self.user_id else None,
            'data_index': self.data_index,
            'ceigall_value': self.ceigall_value,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class BidSynopsisExtractedValue(Base):
    """
    Stores edited extracted values for bid synopsis.
    Allows users to customize extracted numeric values for each requirement.
    """
    __tablename__ = 'bid_synopsis_extracted_values'

    # Primary Keys
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tender_id = Column(String, nullable=False, index=True)  # tender_ref_number
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True, index=True)

    # Data Index (position in the requirements array)
    value_index = Column(Integer, nullable=False)

    # Extracted value
    extracted_value = Column(Text, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                       onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    def to_dict(self):
        """Convert SQLAlchemy model to dictionary for API responses."""
        return {
            'id': str(self.id),
            'tender_id': self.tender_id,
            'user_id': str(self.user_id) if self.user_id else None,
            'value_index': self.value_index,
            'extracted_value': self.extracted_value,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
