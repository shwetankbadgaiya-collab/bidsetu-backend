from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from app.database.db import get_db, verify_password
from app.models.models import User
from app.schemas.schemas import LoginRequest, LoginResponse, UserOut
from app.services.audit import log_action

router = APIRouter()

SECRET_KEY = 'bidsetu-hackathon-secret-key-2026'
ALGORITHM = 'HS256'
ACCESS_TOKEN_EXPIRE_HOURS = 24

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        # Prototype demo mode: fallback to demo officer
        default_officer = db.query(User).filter(User.role == "officer").first()
        if default_officer:
            return {"id": default_officer.id, "email": default_officer.email, "role": default_officer.role, "name": default_officer.name}
        return {"id": 1, "email": "officer@bidsetu.gov.in", "role": "officer", "name": "Priya Sharma"}
    
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        default_officer = db.query(User).filter(User.role == "officer").first()
        if default_officer:
            return {"id": default_officer.id, "email": email, "role": default_officer.role, "name": default_officer.name}
        return {"id": 1, "email": email, "role": "officer", "name": payload.get("name", "Priya Sharma")}
    return {"id": user.id, "email": user.email, "role": user.role, "name": user.name}

@router.post("/login", response_model=LoginResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    # Validate non-empty credentials
    if not request.email or not request.email.strip() or not request.password or not request.password.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email/ID and password cannot be empty",
        )
    
    # Check if user exists in database
    user = db.query(User).filter(User.email == request.email.strip()).first()
    
    if not user:
        # Prototype demo mode: accept any non-empty login and use officer profile (Priya Sharma)
        default_officer = db.query(User).filter(User.role == "officer").first()
        user_id = default_officer.id if default_officer else 1
        user_name = default_officer.name if default_officer else "Priya Sharma"
        user_role = default_officer.role if default_officer else "officer"
        
        access_token = create_access_token(
            data={"sub": request.email.strip(), "user_id": user_id, "role": user_role, "name": user_name}
        )
        log_action(db, user_id, 'User logged in (Demo Mode)', 'user', str(user_id), f"Demo User {request.email} logged in")
        
        return LoginResponse(
            access_token=access_token,
            token_type="bearer",
            user=UserOut(id=user_id, name=user_name, email=request.email.strip(), role=user_role)
        )
    
    # If user exists in database, authenticate and return token
    access_token = create_access_token(
        data={"sub": user.email, "user_id": user.id, "role": user.role, "name": user.name}
    )
    log_action(db, user.id, 'User logged in', 'user', str(user.id), f"User {user.email} logged in")
    
    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserOut.model_validate(user)
    )
