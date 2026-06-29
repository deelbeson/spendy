from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import User
from app.auth import hash_password, verify_password, get_current_user

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, db: Session = Depends(get_db)):
    # If already logged in, redirect to dashboard
    user = get_current_user(request, db)
    if user:
        return RedirectResponse(url="/", status_code=302)

    # If no users exist, redirect to setup
    user_count = db.query(User).count()
    if user_count == 0:
        return RedirectResponse(url="/setup", status_code=302)

    return templates.TemplateResponse("login.html", {
        "request": request,
        "error": request.session.pop("flash_error", None),
    })


@router.post("/login")
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.hashed_password):
        request.session["flash_error"] = "Invalid username or password."
        return RedirectResponse(url="/login", status_code=302)

    request.session["user_id"] = user.id
    return RedirectResponse(url="/", status_code=302)


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=302)


@router.get("/setup", response_class=HTMLResponse)
def setup_page(request: Request, db: Session = Depends(get_db)):
    # Only allow setup if no users exist
    user_count = db.query(User).count()
    if user_count > 0:
        return RedirectResponse(url="/login", status_code=302)

    return templates.TemplateResponse("setup.html", {
        "request": request,
        "error": request.session.pop("flash_error", None),
    })


@router.post("/setup")
def setup(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db),
):
    # Only allow setup if no users exist
    user_count = db.query(User).count()
    if user_count > 0:
        return RedirectResponse(url="/login", status_code=302)

    if password != confirm_password:
        request.session["flash_error"] = "Passwords do not match."
        return RedirectResponse(url="/setup", status_code=302)

    if len(password) < 8:
        request.session["flash_error"] = "Password must be at least 8 characters."
        return RedirectResponse(url="/setup", status_code=302)

    if len(username) < 3:
        request.session["flash_error"] = "Username must be at least 3 characters."
        return RedirectResponse(url="/setup", status_code=302)

    user = User(username=username, hashed_password=hash_password(password))
    db.add(user)
    db.commit()

    return RedirectResponse(url="/login", status_code=302)
