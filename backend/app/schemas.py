from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from .models import Priority, Role, Status


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    role: Role
    is_active: bool


class UserBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: str


class RegisterIn(BaseModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=255)
    full_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class UserAdminUpdate(BaseModel):
    role: Role | None = None
    is_active: bool | None = None


class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=255)


class CategoryOut(CategoryIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


class TicketCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=10, max_length=5000)
    category_id: int
    priority: Priority = Priority.MEDIUM


class TicketStatusUpdate(BaseModel):
    status: Status


class TicketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    priority: Priority
    status: Status
    category: CategoryOut
    created_by: UserBrief
    assigned_to: UserBrief | None
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None


class MetaOut(BaseModel):
    priorities: list[Priority]
    statuses: list[Status]
    roles: list[Role]
    status_transitions: dict[Status, list[Status]]
