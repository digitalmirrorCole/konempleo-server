
from datetime import datetime, timedelta
import os
from typing import  Optional
from aiohttp import ClientError
import boto3
from botocore.config import Config
from fastapi.encoders import jsonable_encoder
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from app.deps import get_db
from app.auth.authDTO import TokenData, UserToken
from sqlalchemy.orm import Session
from jose import jwt, JWTError

from models.models import Users

oauth2_scheme = OAuth2PasswordBearer("/login")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def authenticate_user(db: Session, email: str, password: str):
     user = getUserByEmail(db=db, email= email)
     if not user:
          raise HTTPException(status_code=401, detail="Could not validate credentials", headers={"WWW-Authenticate":"Bearer"})
     if not verify_password(password, user.password):
          raise HTTPException(status_code=401, detail="Could not validate credentials", headers={"WWW-Authenticate":"Bearer"})
     if user.must_change_password:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="You must change your password before continuing."
        )
     return user

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def getUserByEmail(db: Session, email: str) -> Optional[Users]:
        return db.query(Users).filter(Users.email == email).first()

def create_token(data: dict, expires_delta: Optional[datetime]):
    data_copy = data.copy()
    if expires_delta is None:
         expires = datetime.utcnow() + timedelta(minutes=15)
    else:
         expires = datetime.utcnow() + expires_delta
    data_copy.update({"exp":expires})
    token_jwt = jwt.encode(data_copy, key=os.getenv('SECRET_KEY'), algorithm=os.getenv('ALGORITHM'))
    return token_jwt

def generate_token(db: Session, username:str, password: str):
    user = authenticate_user(db, username, password)
    if not user:
        raise HTTPException(status_code=401, detail="Could not validate credentials", headers={"WWW-Authenticate":"Bearer"})
    access_token_expires = timedelta(minutes=int(os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES')))
    payload = {}
    payload["sub"] = user.email
    payload["fullname"] = user.fullname 
    payload["role"] =  user.role
    payload["id"] = user.id
    return create_token(
        data=payload, expires_delta=access_token_expires
    )

def get_user_current(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)):
     try:
         token_decoded = jwt.decode(token, os.getenv('SECRET_KEY'), algorithms=[os.getenv('ALGORITHM')])
         username = token_decoded.get("sub")
         if username == None:
              raise HTTPException(status_code=401, detail="Could not validate credentials", headers={"WWW-Authenticate":"Bearer"})
         token_data = TokenData(username=username)
     except JWTError:
        raise HTTPException(status_code=401, detail="Could not validate credentials", headers={"WWW-Authenticate":"Bearer"})
     user = getUserByEmail(db=db, email= token_data.username)
     if user is None:
         raise HTTPException(status_code=401, detail="Could not validate credentials", headers={"WWW-Authenticate":"Bearer"})
     user_data_token = UserToken(**{'email':username, 'fullname': token_decoded.get("fullname"), 
                                                    'role':token_decoded.get("role"),
                                                    'id':token_decoded.get("id")})
     return user_data_token
     
def get_password_hash(password):
    return pwd_context.hash(password)


S3_BUCKET_NAME = os.getenv("BUCKET_NAME")

s3_client = boto3.client(
    's3',
    aws_access_key_id= os.getenv("AWS_KEY"),
    aws_secret_access_key=os.getenv("AWS_SECRET_KEY"),
    config=Config(signature_version='s3v4')
)

def generate_presigned_url(object_key: str, expiration: int = 3600) -> str:
    try:
        response = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': S3_BUCKET_NAME, 'Key': object_key},
            ExpiresIn=expiration
        )
        return response
    except ClientError as e:
        raise Exception(f"Failed to generate pre-signed URL: {e}")
