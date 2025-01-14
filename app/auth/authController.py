import os
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.auth.authDTO import Token, UpdatePassword
from app.auth.authService import generate_presigned_url, generate_token, get_password_hash, getUserByEmail, verify_password
from app import deps


authRouter = APIRouter()
authRouter.tags = ['Auth']

@authRouter.post("/login")
def login_for_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(deps.get_db)):
    access_token = generate_token(db=db, username=form_data.username, password=form_data.password)
    return Token(access_token = access_token, token_type="bearer")

@authRouter.post("/change-password")
def change_password(form_data: UpdatePassword, db: Session = Depends(deps.get_db)):
    user = getUserByEmail(db=db, email= form_data.email)
    if not user or not verify_password(form_data.current_password, user.password):
        raise HTTPException(status_code=400, detail="Invalid credentials")
    hashed_new_password = get_password_hash(form_data.new_password)
    user.password = hashed_new_password
    user.must_change_password = False

    db.commit()

    return {"msg": "Password changed successfully"}

@authRouter.get("/generate-presigned-url/")
def get_presigned_url(file_path: str, db: Session = Depends(deps.get_db)):
    try:
        url = generate_presigned_url(file_path)
        return {"url": url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating pre-signed URL: {str(e)}")
