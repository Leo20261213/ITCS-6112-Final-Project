"""US-02: As an administrator, I want role-based access so that users ONLY access authorized features.
US-05 (admin side): administrators manage the ticket categories used to organize tickets."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Category, Role, Ticket, User
from ..schemas import CategoryIn, CategoryOut, UserAdminUpdate, UserOut
from ..security import require_roles

router = APIRouter(prefix="/api/admin", tags=["admin"])
admin_only = require_roles(Role.ADMIN)


@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), _: User = Depends(admin_only)):
    return db.scalars(select(User).order_by(User.id)).all()


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, body: UserAdminUpdate, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if user.id == admin.id and (body.role not in (None, Role.ADMIN) or body.is_active is False):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot remove your own administrator access")
    if body.role is not None:
        if user.role == Role.AGENT and body.role != Role.AGENT:
            # Release this agent's tickets so they are not stranded with a non-agent.
            for t in db.scalars(select(Ticket).where(Ticket.assigned_to_id == user.id)):
                t.assigned_to_id = None
        user.role = body.role
    if body.is_active is not None:
        user.is_active = body.is_active
    db.commit()
    db.refresh(user)
    return user


@router.post("/categories", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
def create_category(body: CategoryIn, db: Session = Depends(get_db), _: User = Depends(admin_only)):
    name = body.name.strip()
    if db.scalar(select(Category).where(func.lower(Category.name) == name.lower())):
        raise HTTPException(status.HTTP_409_CONFLICT, "Category already exists")
    category = Category(name=name, description=body.description.strip())
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(category_id: int, db: Session = Depends(get_db), _: User = Depends(admin_only)):
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Category not found")
    if db.scalar(select(func.count()).select_from(Ticket).where(Ticket.category_id == category_id)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Category is in use by existing tickets")
    db.delete(category)
    db.commit()
