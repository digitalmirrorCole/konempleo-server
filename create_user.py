from datetime import datetime
from sqlalchemy.orm import Session
import sys
from app.auth import authService
from db.session import SessionLocal
from models.models import UserEnum, Users


def create_user(email: str, password: str, role: str, fullname: str):
    db: Session = SessionLocal()

    # Validate role
    try:
        role_enum = UserEnum[role]
    except KeyError:
        valid_roles = [e.name for e in UserEnum]
        print(f"Invalid role provided. Valid roles are: {', '.join(valid_roles)}")
        return

    # Check if a user with the given email already exists
    existing_user = db.query(Users).filter(Users.email == email).first()
    if existing_user:
        print("A user with this email already exists!")
        return

    # Create the new user
    new_user = Users(
        email=email,
        fullname=fullname,
        password=authService.get_password_hash(password),
        must_change_password=False,
        role=role_enum,  # Set the role based on the input
        active=True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    print(f"User '{fullname}' with role '{role}' created successfully!")


if __name__ == "__main__":
    # Ensure the correct number of arguments
    if len(sys.argv) != 5:
        print("Usage: python create_user.py <email> <password> <role> <fullname>")
        sys.exit(1)

    email = sys.argv[1]
    password = sys.argv[2]
    role = sys.argv[3]
    fullname = sys.argv[4]

    create_user(email, password, role, fullname)
