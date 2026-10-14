from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.deps import CurrentUser, DbSession
from app.models import User
from app.schemas import Token, UserCreate, UserLogin, UserOut
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["Auth"])


def _invalid_credentials() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect email or password",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _authenticate(db, email: str, password: str) -> User:
    user = db.scalar(select(User).where(User.email == email.strip().lower()))
    if user is None or not verify_password(password, user.hashed_password):
        raise _invalid_credentials()
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")
    return user


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: DbSession):
    if db.scalar(select(User.id).where(User.email == payload.email)) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:  # race condition: two simultaneous registrations
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Email already registered")
    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
def login(payload: UserLogin, db: DbSession):
    """Login with ONLY email and password."""
    user = _authenticate(db, payload.email, payload.password)
    token, expires_in = create_access_token(user.id)
    return Token(access_token=token, expires_in=expires_in)


@router.get("/me", response_model=UserOut)
def me(current_user: CurrentUser):
    return current_user
