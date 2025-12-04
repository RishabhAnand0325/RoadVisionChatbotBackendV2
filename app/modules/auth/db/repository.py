from sqlalchemy.orm import Session
from typing import Optional

from .schema import User, TokenBlocklist
from ..models.pydantic_models import UserCreate, UserProfileUpdate
from ..security import get_password_hash

class AuthRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_email(self, email: str) -> Optional[User]:
        return self.db.query(User).filter(User.email == email).first()

    def create(self, user: UserCreate) -> User:
        hashed_password = get_password_hash(user.password)
        db_user = User(
            email=user.email,
            hashed_password=hashed_password,
            full_name=user.full_name,
            employee_id=user.employee_id,
            mobile_number=user.mobile_number,
            designation=user.designation,
            department=user.department,
        )
        self.db.add(db_user)
        self.db.commit()
        self.db.refresh(db_user)
        return db_user
    
    def update(self, user: User, updates: UserProfileUpdate) -> User:
        update_data = updates.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(user, key, value)
        self.db.commit()
        self.db.refresh(user)
        return user

    def update_password(self, user: User, new_password: str) -> User:
        user.hashed_password = get_password_hash(new_password)
        self.db.commit()
        self.db.refresh(user)
        return user

class TokenBlocklistRepository:
    def __init__(self, db: Session):
        self.db = db

    def add_to_blocklist(self, jti: str) -> None:
        blocklisted_token = TokenBlocklist(jti=jti)
        self.db.add(blocklisted_token)
        self.db.commit()
    
    def is_token_blocklisted(self, jti: str) -> bool:
        return self.db.query(TokenBlocklist).filter(TokenBlocklist.jti == jti).first() is not None
