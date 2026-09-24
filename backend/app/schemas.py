from datetime import datetime

from pydantic import BaseModel, Field


class LaunchIn(BaseModel):
    init_data: str | None = None
    dev_user_id: str | None = None


class UserOut(BaseModel):
    id: int
    role: str
    region_code: str | None
    city: str | None
    grade: int | None
    type_codes: list[str]
    goal_codes: list[str]
    subject_codes: list[str]
    notifications_enabled: bool
    onboarded: bool


class LaunchOut(BaseModel):
    token: str
    user: UserOut
    is_new: bool
    start_param: str | None = None


class ProfileIn(BaseModel):
    region_code: str | None = None
    city: str | None = None
    type_codes: list[str] | None = None
    grade: int | None = Field(default=None, ge=1, le=11)
    goal_codes: list[str] | None = None
    subject_codes: list[str] | None = None


class ParticipationIn(BaseModel):
    event_id: int
    status: str = "going"


class ParticipationPatch(BaseModel):
    status: str


class ParticipationOut(BaseModel):
    id: int
    event_id: int
    status: str
    updated_at: datetime


class CalendarItemOut(BaseModel):
    event_id: int
    slug: str
    type: str
    kind: str
    at: datetime
    title: str


class DemoReminderIn(BaseModel):
    event_id: int
    delay_seconds: int = Field(default=10, ge=0, le=3600)


class ShareOut(BaseModel):
    token: str
    deep_link: str
    share_url: str
    share_text: str
