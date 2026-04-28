"""
Authentication routes — register and login.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.deps import get_db, get_current_user
from api.core.passwords import hash_password, verify_password
from api.schemas.auth import RegisterNGORequest, RegisterVolunteerRequest, LoginRequest, AuthResponse
from api.models.user import User, UserRole
from api.models.ngo import NGO
from api.models.volunteer import Volunteer
import uuid

router = APIRouter()


@router.post("/register/ngo", response_model=dict)
async def register_ngo(
    req: RegisterNGORequest,
    db: Session = Depends(get_db),
):
    """
    Register a new NGO manager account.
    TODO: Integrate with Firebase Auth to create user account and get firebase_uid.
    """
    # TODO: Call Firebase to create account
    # firebase_uid = await firebase_create_user(req.email, req.password)

    existing = db.query(User).filter(User.email == req.email).first()
    if existing and existing.password_hash:
        raise HTTPException(status_code=400, detail="User already registered")

    if existing:
        firebase_uid = existing.firebase_uid
        existing.password_hash = hash_password(req.password)
        existing.role = UserRole.NGO_MANAGER
    else:
        firebase_uid = req.email
        user = User(
            firebase_uid=firebase_uid,
            email=req.email,
            password_hash=hash_password(req.password),
            role=UserRole.NGO_MANAGER,
        )
        db.add(user)
    db.flush()
    
    ngo = db.query(NGO).filter(NGO.firebase_uid == firebase_uid).first()
    if ngo:
        ngo_id = ngo.ngo_id
        ngo.org_name = req.org_name
        ngo.org_registration_number = req.org_registration_number or None
        ngo.allowed_categories = req.allowed_categories or []
        ngo.custom_subtypes = req.custom_subtypes or {}
    else:
        ngo_id = f"ngo_{uuid.uuid4().hex[:12]}"
        ngo = NGO(
            ngo_id=ngo_id,
            firebase_uid=firebase_uid,
            org_name=req.org_name,
            org_registration_number=req.org_registration_number or None,
            allowed_categories=req.allowed_categories or [],
            custom_subtypes=req.custom_subtypes or {},
            is_verified=False,
        )
        db.add(ngo)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        message = str(getattr(exc, "orig", exc)).lower()
        if "org_registration_number" in message or "unique" in message:
            raise HTTPException(status_code=400, detail="Organization registration number already exists") from exc
        if "firebase_uid" in message and "foreign key" in message:
            raise HTTPException(status_code=500, detail="Registration failed due to data dependency error") from exc
        raise HTTPException(status_code=400, detail="Unable to register NGO with provided details") from exc

    return {"message": "NGO registered successfully", "ngo_id": ngo_id}


@router.post("/register/volunteer", response_model=dict)
async def register_volunteer(
    req: RegisterVolunteerRequest,
    db: Session = Depends(get_db),
):
    """Register a new volunteer account."""
    existing = db.query(User).filter(User.email == req.email).first()
    if existing and existing.password_hash:
        raise HTTPException(status_code=400, detail="User already registered")

    if existing:
        firebase_uid = existing.firebase_uid
        existing.password_hash = hash_password(req.password)
        existing.role = UserRole.VOLUNTEER
    else:
        firebase_uid = req.email
        user = User(
            firebase_uid=firebase_uid,
            email=req.email,
            password_hash=hash_password(req.password),
            role=UserRole.VOLUNTEER,
        )
        db.add(user)
    db.flush()

    volunteer = db.query(Volunteer).filter(Volunteer.firebase_uid == firebase_uid).first()
    if volunteer:
        volunteer_id = volunteer.volunteer_id
        volunteer.full_name = req.full_name
        volunteer.age = req.age
        volunteer.phone = req.phone
        volunteer.city = req.city
        volunteer.state = req.state
        volunteer.lat = req.lat
        volunteer.lng = req.lng
        volunteer.willing_to_travel_km = req.willing_to_travel_km
        volunteer.skills = req.skills or []
        volunteer.preferred_categories = req.preferred_categories or []
        volunteer.strengths = req.strengths
        volunteer.past_experience = req.past_experience
    else:
        volunteer_id = f"vol_{uuid.uuid4().hex[:12]}"
        volunteer = Volunteer(
            volunteer_id=volunteer_id,
            firebase_uid=firebase_uid,
            full_name=req.full_name,
            age=req.age,
            phone=req.phone,
            city=req.city,
            state=req.state,
            lat=req.lat,
            lng=req.lng,
            willing_to_travel_km=req.willing_to_travel_km,
            skills=req.skills or [],
            preferred_categories=req.preferred_categories or [],
            strengths=req.strengths,
            past_experience=req.past_experience,
        )
        db.add(volunteer)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="Unable to register volunteer with provided details") from exc

    return {"message": "Volunteer registered successfully", "volunteer_id": volunteer_id}


@router.post("/login", response_model=AuthResponse)
async def login(req: LoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate email + password against PostgreSQL.
    TODO: Replace with Firebase Auth if/when you move auth fully to Firebase.
    """
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    role_value = user.role.value if hasattr(user.role, "value") else str(user.role)
    access_token = f"local:{user.firebase_uid}:{role_value}"

    return AuthResponse(
        access_token=access_token,
        token_type="bearer",
        user_id=user.firebase_uid,
        role=role_value,
    )
