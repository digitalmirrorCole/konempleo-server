from datetime import datetime
from sqlalchemy.orm import Session

from app.auth import authService
from db.session import SessionLocal
from models.models import UserEnum, Users

def create_superadmin(email: str, password: str,):
    db: Session = SessionLocal()

    # Check if a superadmin with the given email or username already exists
    existing_superadmin = db.query(Users).filter(
        (Users.role == UserEnum.super_admin) | (Users.email == email)
    ).first()
    if existing_superadmin:
        print("A user with these credentials already exists!")
        return

    # Create the new superadmin user
    new_superadmin = Users(
        email=email,
        fullname= "admin user",
        password= authService.get_password_hash(password),
        must_change_password = False,
        role=UserEnum.super_admin,  # Set the role to super_admin
        active=True, 
    )
    db.add(new_superadmin)
    db.commit()
    db.refresh(new_superadmin)
    print("Superadmin created successfully!")

if __name__ == "__main__":
    # Example usage:
    create_superadmin("admin@example.com", "supersecretpassword")
