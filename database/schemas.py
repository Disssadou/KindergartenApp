from pydantic import BaseModel, EmailStr, Field, model_validator
from typing import Any, List, Optional, Dict
from datetime import date, datetime
from .models import (
    UserRole,
    # PaymentStatus, # УДАЛЕНО (предполагая, что Payment модель тоже удалена)
    NotificationType, # Оставляем
    MediaType,        # Оставляем
    MealType,         # Оставляем
    AbsenceType,      # Оставляем
    # TransactionType,  # УДАЛЕНО
    NotificationAudience, # Оставляем
)
from pydantic import field_validator


# --- Общие конфигурации ---
# class BaseConfig: # Убрали, т.к. model_config используется в Pydantic v2
# from_attributes = True


# --- Media Schemas --- (Оставляем uploaded_at)
class MediaBase(BaseModel):
    original_filename: str
    mime_type: str
    file_type: MediaType

class MediaRead(MediaBase):
    id: int
    file_path: str
    thumbnail_path: Optional[str] = None
    uploaded_at: datetime # Это аналог created_at для медиа, оставляем
    model_config = {"from_attributes": True}


# --- UserSimple Schema --- (без created_at/updated_at)
class UserSimple(BaseModel):
    id: int
    username: str
    full_name: str
    model_config = {"from_attributes": True} # Добавил


# --- Post Schemas ---
class PostBase(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    text_content: str
    is_pinned: Optional[bool] = False

class PostCreate(PostBase):
    pass

class PostUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    text_content: Optional[str] = None
    is_pinned: Optional[bool] = None

class PostRead(PostBase):
    id: int
    author_id: Optional[int] = None
    author: Optional[UserSimple] = None
    created_at: datetime # Оставляем
    # updated_at: datetime # УДАЛЕНО
    media_files: List[MediaRead] = []
    model_config = {"from_attributes": True}


# --- Group Schemas ---
class GroupBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    age_min: Optional[int] = Field(None, ge=0)
    age_max: Optional[int] = Field(None, ge=0)
    capacity: Optional[int] = Field(None, ge=1)

class GroupCreate(GroupBase):
    teacher_id: Optional[int] = None

class GroupUpdate(GroupBase): # ... без изменений в полях, но created_at/updated_at не будет в ответе
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    teacher_id: Optional[int] = None
    description: Optional[str] = None
    age_min: Optional[int] = Field(None, ge=0)
    age_max: Optional[int] = Field(None, ge=0)
    capacity: Optional[int] = Field(None, ge=1)

class GroupSimple(BaseModel):
    id: int
    name: str
    model_config = {"from_attributes": True}

class GroupRead(GroupBase):
    id: int
    teacher_id: Optional[int] = None
    # created_at: datetime # УДАЛЕНО
    # updated_at: datetime # УДАЛЕНО (если было)
    model_config = {"from_attributes": True}


# --- Child Schemas ---
class ChildBase(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=100)
    birth_date: date # В модели это String (зашифрованный), но API будет принимать/отдавать date
    address: Optional[str] = Field(None, max_length=500)
    medical_info: Optional[str] = None

class ChildCreate(ChildBase):
    group_id: Optional[int] = None

class ChildUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=1, max_length=100)
    birth_date: Optional[date] = None
    group_id: Optional[int] = None
    address: Optional[str] = Field(None, max_length=500)
    medical_info: Optional[str] = None

class ChildParentLink(BaseModel): # ... без изменений
    parent_id: int
    relation_type: str = Field(..., max_length=50)

class ChildParentUnlink(BaseModel): # ... без изменений
    parent_id: int

class ChildSimple(BaseModel): # ... без изменений (уже адаптирована)
    id: int
    full_name: str
    last_charge_amount: Optional[float] = None
    last_charge_year: Optional[int] = None
    last_charge_month: Optional[int] = None
    model_config = {"from_attributes": True}

class ChildRead(ChildBase):
    id: int
    group_id: Optional[int] = None
    group: Optional[GroupSimple] = None
    created_at: datetime # Оставляем
    # updated_at: datetime # УДАЛЕНО
    model_config = {"from_attributes": True}


# --- User Schemas ---
class UserBase(BaseModel): # ... без изменений
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_]+$")
    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)

class UserCreate(UserBase): # ... без изменений
    password: str = Field(..., min_length=6)
    role: UserRole = UserRole.PARENT

class UserUpdate(BaseModel): # ... без изменений
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, min_length=1, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)

class UserUpdateRole(BaseModel): # ... без изменений
    role: UserRole

class UserUpdatePassword(BaseModel): # ... без изменений
    current_password: str
    new_password: str = Field(..., min_length=6)

class UserSetFcmToken(BaseModel): # ... без изменений
    fcm_token: Optional[str] = Field(None, max_length=255)

class UserRead(UserBase):
    id: int
    role: UserRole
    created_at: datetime # Оставляем
    # updated_at: datetime # УДАЛЕНО
    last_login: Optional[datetime] = None
    fcm_token: Optional[str] = None
    model_config = {"from_attributes": True}


# --- ChildParent Schemas ---
class ChildParentRead(BaseModel):
    child_id: int
    parent_id: int
    relation_type: Optional[str] = None # Сделал Optional, как было в твоем коде
    child: ChildSimple
    parent: UserSimple
    # created_at: datetime # УДАЛЕНО
    # updated_at: datetime # УДАЛЕНО
    model_config = {"from_attributes": True}


# --- Attendance Schemas ---
class AttendanceBase(BaseModel): # ... без изменений
    date: date
    present: bool = False
    absence_reason: Optional[str] = Field(None, max_length=200)
    absence_type: Optional[AbsenceType] = None

class AttendanceCreate(AttendanceBase): # ... без изменений
    child_id: int

class AttendanceUpdate(BaseModel): # ... без изменений
    present: Optional[bool] = None
    absence_reason: Optional[str] = Field(None, max_length=200)
    absence_type: Optional[AbsenceType] = None

class AttendanceRead(AttendanceBase):
    id: int
    child_id: int
    created_by: Optional[int] = None # Оставляем
    created_at: datetime # Оставляем
    # updated_at: datetime # УДАЛЕНО
    child: Optional[ChildSimple] = None
    model_config = {"from_attributes": True}

class BulkAttendanceItem(BaseModel): # ... без изменений
    child_id: int
    present: bool
    absence_reason: Optional[str] = Field(None, max_length=200)
    absence_type: Optional[AbsenceType] = None

class BulkAttendanceRecord(BaseModel): # Оставляем, если где-то используется
    child_id: int
    present: bool

class BulkAttendanceCreate(BaseModel): # ... без изменений
    group_id: int
    date: date
    attendance_list: List[BulkAttendanceItem]


# --- Event Schemas ---
class EventBase(BaseModel): # ... без изменений
    title: str = Field(..., max_length=200)
    description: Optional[str] = None
    event_date: datetime
    group_id: Optional[int] = None

class EventCreate(EventBase): # ... без изменений
    pass

class EventUpdate(BaseModel): # ... без изменений
    title: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    event_date: Optional[datetime] = None
    group_id: Optional[int] = None

class EventRead(EventBase):
    id: int
    created_by: Optional[int] = None
    created_at: datetime # Оставляем
    # updated_at: datetime # УДАЛЕНО
    model_config = {"from_attributes": True}


# --- Notification Schemas ---
class NotificationBase(BaseModel): # ... без изменений
    title: str = Field(..., min_length=3, max_length=255)
    content: str = Field(..., min_length=4)
    is_event: bool = False
    event_date: Optional[datetime] = None
    audience: NotificationAudience = NotificationAudience.ALL
    @model_validator(mode="after") # ... без изменений
    def check_event_date(cls, data: Any) -> Any: # ...
        _is_event = getattr(data, "is_event", False); _event_date = getattr(data, "event_date", None)
        if _is_event is True and _event_date is None: raise ValueError("event_date must be set if is_event is True")
        if _is_event is False and _event_date is not None: data.event_date = None
        return data

class NotificationCreate(NotificationBase): # ... без изменений
    pass

class NotificationUpdate(BaseModel): # ... без изменений
    title: Optional[str] = Field(None, min_length=3, max_length=255)
    content: Optional[str] = Field(None, min_length=10)
    is_event: Optional[bool] = None
    event_date: Optional[datetime] = None
    audience: Optional[NotificationAudience] = None
    @model_validator(mode="after") # ... без изменений
    def check_update_event_date(cls, data: Any) -> Any: # ...
        _is_event = getattr(data, "is_event", None); _event_date = getattr(data, "event_date", None)
        if _is_event is False: data.event_date = None
        return data

class NotificationRead(NotificationBase):
    id: int
    author_id: Optional[int] = None
    created_at: datetime # Оставляем
    # updated_at: datetime # УДАЛЕНО (в твоем последнем файле оно было, но ты решил убрать из модели)
    model_config = {"from_attributes": True}


# --- Meal Menu Schemas ---
class MealMenuBase(BaseModel): # ... без изменений
    date: date
    meal_type: MealType
    description: str = Field(..., min_length=1)

class MealMenuCreate(MealMenuBase): # ... без изменений
    description: Optional[str] = Field(None, min_length=0)

class MealMenuUpdate(BaseModel): # ... без изменений
    description: Optional[str] = Field(None, min_length=1)

class MealMenuRead(MealMenuBase):
    id: int
    created_by: Optional[int] = None
    # created_at: datetime # УДАЛЕНО
    # updated_at: datetime # УДАЛЕНО
    model_config = {"from_attributes": True}


# --- Auth Schemas --- (без изменений)
class Token(BaseModel): # ...
    access_token: str
    token_type: str
class TokenData(BaseModel): # ...
    username: Optional[str] = None; user_id: Optional[int] = None; role: Optional[UserRole] = None


# --- Holiday Schemas --- (created_at остается)
class HolidayBase(BaseModel): # ... без изменений
    date: date
    name: Optional[str] = Field(None, max_length=100)

class HolidayCreate(HolidayBase): # ... без изменений
    pass

class HolidayRead(HolidayBase):
    id: int
    created_at: datetime # Оставляем, т.к. в модели Holiday ты его не удалял
    model_config = {"from_attributes": True}

class HolidayDelete(BaseModel): # ... без изменений
    date: date


# --- Report Schemas --- (без изменений)
# ... (AttendanceReport* схемы остаются как были) ...
class AttendanceReportDayRecord(BaseModel): mark: str; is_weekend: bool = False; is_holiday: bool = False
class AttendanceReportChildSummary(BaseModel): present_days: int = 0; absent_sick_days: int = 0; absent_vacation_days: int = 0; absent_other_days: int = 0; payable_days: int = 0
class AttendanceReportChildData(BaseModel): child_id: int; child_name: str; account_number: Optional[str] = None; days: Dict[str, AttendanceReportDayRecord] = {}; summary: AttendanceReportChildSummary = Field(default_factory=AttendanceReportChildSummary); model_config = {"from_attributes": True}
class AttendanceReportData(BaseModel): year: int; month: int; days_in_month: int; group_id: int; group_name: str; group_description: Optional[str] = None; teacher_name: Optional[str] = None; holiday_dates: List[date] = []; children_data: List[AttendanceReportChildData] = []; daily_totals: Dict[str, int] = {}; total_work_days: int = 0; model_config = {"from_attributes": True}
class AttendanceReportParams(BaseModel): group_id: int = Field(..., ge=1); year: int = Field(..., ge=2020, le=date.today().year + 1); month: int = Field(..., ge=1, le=12); default_rate: Optional[float] = Field(None, ge=0); staff_rates: Optional[Dict[int, float]] = Field(default_factory=dict)


# --- MonthlyCharge Schemas --- (calculated_at это аналог created_at, оставляем)
class MonthlyChargeBase(BaseModel): # ... без изменений ...
    year: int = Field(..., ge=2020); month: int = Field(..., ge=1, le=12); amount_due: float = Field(..., ge=0); calculation_details: Optional[str] = None
class MonthlyChargeCreate(MonthlyChargeBase): # ... без изменений ...
    child_id: int
class MonthlyChargeRead(MonthlyChargeBase): # ... без изменений ...
    id: int; child_id: int; calculated_at: datetime; child: Optional[ChildSimple] = None; model_config = {"from_attributes": True}
class MonthlyChargeCalculationItem(BaseModel): # ... без изменений ...
    child_id: int; day_cost: float = Field(..., ge=0)
class MonthlyChargeCalculationPayload(BaseModel): # ... без изменений ...
    group_id: int = Field(..., ge=1); year: int = Field(..., ge=2020, le=date.today().year + 5); month: int = Field(..., ge=1, le=12); default_day_cost: float = Field(..., ge=0); individual_rates: List[MonthlyChargeCalculationItem] = Field(default_factory=list)