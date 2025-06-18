import enum
from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Date,
    DateTime,
    Boolean,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
    Index,
    BigInteger,
    Numeric,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func

UTC_NOW = func.now()
Base = declarative_base()


# --- Enums ---
class UserRole(str, enum.Enum):
    ADMIN = "admin"
    TEACHER = "teacher"
    PARENT = "parent"


class NotificationType(str, enum.Enum):
    ATTENDANCE = "attendance"
    PAYMENT = "payment"
    EVENT = "event"
    POST = "post"
    SYSTEM = "system"


class MediaType(str, enum.Enum):
    PHOTO = "photo"
    DOCUMENT = "document"
    OTHER = "other"


class MealType(str, enum.Enum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    SNACK = "snack"


class AbsenceType(str, enum.Enum):
    SICK_LEAVE = "sick_leave"
    VACATION = "vacation"
    OTHER = "other"


# --- Модели таблиц ---
class User(Base):
    __tablename__ = "users"
    id = Column(BigInteger, primary_key=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    phone = Column(String(255), nullable=True)
    password_hash = Column(String(128), nullable=False)
    role = Column(String(20), nullable=False, index=True, default=UserRole.PARENT.value)
    created_at = Column(DateTime(timezone=True), server_default=UTC_NOW, nullable=False)
    # updated_at = Column(DateTime(timezone=True),server_default=UTC_NOW,onupdate=UTC_NOW,nullable=False,)
    last_login = Column(DateTime(timezone=True), nullable=True)
    fcm_token = Column(String(255), index=True, nullable=True)

    groups_led = relationship(
        "Group", back_populates="teacher", foreign_keys="[Group.teacher_id]"
    )
    children_relations = relationship(
        "ChildParent", back_populates="parent", cascade="all, delete-orphan"
    )
    attendances_created = relationship(
        "Attendance",
        back_populates="created_by_user",
        foreign_keys="[Attendance.created_by]",
    )
    events_created = relationship(
        "Event", back_populates="created_by_user", foreign_keys="[Event.created_by]"
    )

    media_uploaded = relationship(
        "Media",
        back_populates="uploader",
        foreign_keys="[Media.uploaded_by_id]",
    )
    posts_authored = relationship(
        "Post", back_populates="author", foreign_keys="[Post.author_id]"
    )
    notifications_authored = relationship(
        "Notification", back_populates="author", foreign_keys="[Notification.author_id]"
    )
    __table_args__ = (
        CheckConstraint(role.in_([r.value for r in UserRole]), name="user_role_check"),
        Index("ix_user_role", role),
    )

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', role='{self.role}')>"


class Group(Base):
    __tablename__ = "groups"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    teacher_id = Column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    age_min = Column(Integer, nullable=True)
    age_max = Column(Integer, nullable=True)
    capacity = Column(Integer, nullable=True)
    # created_at = Column(DateTime(timezone=True), server_default=UTC_NOW, nullable=False)
    # updated_at = Column(DateTime(timezone=True),server_default=UTC_NOW,onupdate=UTC_NOW,nullable=False,)

    teacher = relationship("User", back_populates="groups_led")
    children = relationship("Child", back_populates="group")
    events = relationship("Event", back_populates="group", cascade="all, delete-orphan")

    media_files = relationship(
        "Media",
        back_populates="group",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Group(id={self.id}, name='{self.name}')>"


class Child(Base):
    __tablename__ = "children"
    id = Column(BigInteger, primary_key=True)
    full_name = Column(String(255), nullable=False, index=True)
    birth_date = Column(String(255), nullable=False)
    group_id = Column(
        Integer, ForeignKey("groups.id", ondelete="SET NULL"), nullable=True, index=True
    )
    address = Column(String(512), nullable=True)
    medical_info = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=UTC_NOW, nullable=False)
    # updated_at = Column(DateTime(timezone=True),server_default=UTC_NOW,onupdate=UTC_NOW,nullable=False,)

    group = relationship("Group", back_populates="children")
    attendances = relationship(
        "Attendance", back_populates="child", cascade="all, delete-orphan"
    )

    parent_relations = relationship(
        "ChildParent", back_populates="child", cascade="all, delete-orphan"
    )
    monthly_charges = relationship(
        "MonthlyCharge",
        back_populates="child",
        cascade="all, delete-orphan",
        order_by="desc(MonthlyCharge.year), desc(MonthlyCharge.month)",
    )

    def __repr__(self):
        return f"<Child(id={self.id}, full_name='{self.full_name}')>"


class ChildParent(Base):
    __tablename__ = "child_parents"
    child_id = Column(
        BigInteger, ForeignKey("children.id", ondelete="CASCADE"), primary_key=True
    )
    parent_id = Column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    relation_type = Column(String(50), nullable=True)
    # created_at = Column(DateTime(timezone=True), server_default=UTC_NOW, nullable=False)
    # updated_at = Column(DateTime(timezone=True), server_default=UTC_NOW, onupdate=UTC_NOW, nullable=False)
    child = relationship("Child", back_populates="parent_relations")
    parent = relationship("User", back_populates="children_relations")

    def __repr__(self):
        return f"<ChildParent(c_id={self.child_id}, p_id={self.parent_id})>"


class Attendance(Base):

    __tablename__ = "attendances"
    id = Column(BigInteger, primary_key=True)
    child_id = Column(
        BigInteger,
        ForeignKey("children.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    date = Column(Date, nullable=False, index=True)
    present = Column(Boolean, nullable=False, default=False)
    absence_reason = Column(String(200), nullable=True)
    absence_type = Column(
        String(20), nullable=True, index=True, comment="sick_leave, vacation, other"
    )
    created_by = Column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    created_at = Column(DateTime(timezone=True), server_default=UTC_NOW, nullable=False)
    # updated_at = Column(DateTime(timezone=True),server_default=UTC_NOW,onupdate=UTC_NOW,nullable=False,)
    child = relationship("Child", back_populates="attendances")
    created_by_user = relationship("User", back_populates="attendances_created")
    __table_args__ = (
        UniqueConstraint("child_id", "date", name="uq_attendance_child_date"),
        Index("ix_attendance_date", date),
        Index("ix_attendance_absence_type", absence_type),
        CheckConstraint(
            absence_type.in_([at.value for at in AbsenceType] + [None]),
            name="attendance_absence_type_check",
        ),
        CheckConstraint(
            (absence_type.is_(None) & absence_reason.is_(None)) | (present == False),
            name="attendance_reason_only_if_absent",
        ),
    )

    def __repr__(self):
        status = "Present" if self.present else "Absent"
        return f"<Attendance(id={self.id}, c_id={self.child_id}, date='{self.date}', status='{status}')>"


class Event(Base):

    __tablename__ = "events"
    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    event_date = Column(DateTime(timezone=True), nullable=False, index=True)
    group_id = Column(
        Integer, ForeignKey("groups.id", ondelete="CASCADE"), index=True, nullable=True
    )
    created_by = Column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at = Column(DateTime(timezone=True), server_default=UTC_NOW, nullable=False)
    # updated_at = Column(DateTime(timezone=True),server_default=UTC_NOW,onupdate=UTC_NOW,nullable=False,)
    group = relationship("Group", back_populates="events")
    created_by_user = relationship("User", back_populates="events_created")

    def __repr__(self):
        return f"<Event(id={self.id}, title='{self.title}', date='{self.event_date}')>"


class Post(Base):
    __tablename__ = "posts"
    id = Column(BigInteger, primary_key=True, index=True)
    title = Column(String(255), nullable=True)
    text_content = Column(Text, nullable=False)
    author_id = Column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    is_pinned = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=UTC_NOW, nullable=False)
    # updated_at = Column(DateTime(timezone=True),server_default=UTC_NOW,onupdate=UTC_NOW,nullable=False,)

    author = relationship("User", back_populates="posts_authored")

    media_files = relationship(
        "Media", back_populates="post", cascade="all, delete-orphan", lazy="selectin"
    )

    def __repr__(self):
        return f"<Post(id={self.id}, title='{self.title[:20]}...')>"


class Media(Base):
    __tablename__ = "media"
    id = Column(BigInteger, primary_key=True, index=True)
    post_id = Column(
        BigInteger,
        ForeignKey("posts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    group_id = Column(
        Integer, ForeignKey("groups.id", ondelete="SET NULL"), nullable=True, index=True
    )

    file_path = Column(String(512), nullable=False, unique=True)
    thumbnail_path = Column(String(512), nullable=True, unique=True)
    original_filename = Column(String(255), nullable=False)
    mime_type = Column(String(100), nullable=False)
    file_type = Column(
        String(50), nullable=False, index=True, default=MediaType.OTHER.value
    )

    uploaded_by_id = Column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    uploaded_at = Column(
        DateTime(timezone=True), server_default=UTC_NOW, nullable=False
    )

    post = relationship("Post", back_populates="media_files")
    uploader = relationship(
        "User", back_populates="media_uploaded", foreign_keys=[uploaded_by_id]
    )
    group = relationship("Group", back_populates="media_files")

    __table_args__ = (
        CheckConstraint(
            file_type.in_([mt.value for mt in MediaType]), name="media_file_type_check"
        ),
    )

    def __repr__(self):
        return f"<Media(id={self.id}, p_id={self.post_id}, g_id={self.group_id}, type='{self.file_type}')>"


class MealMenu(Base):

    __tablename__ = "meal_menus"
    id = Column(BigInteger, primary_key=True)
    date = Column(Date, nullable=False, index=True)
    meal_type = Column(String(20), nullable=False, index=True)
    description = Column(Text, nullable=False)
    created_by = Column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # created_at = Column(DateTime(timezone=True), server_default=UTC_NOW, nullable=False)
    # updated_at = Column(DateTime(timezone=True),server_default=UTC_NOW,onupdate=UTC_NOW,nullable=False,)
    creator = relationship("User")
    __table_args__ = (
        UniqueConstraint("date", "meal_type", name="uq_mealmenu_date_type"),
        CheckConstraint(
            meal_type.in_([m.value for m in MealType]), name="mealmenu_type_check"
        ),
        Index("ix_mealmenu_date_type", "date", "meal_type"),
    )

    def __repr__(self):
        return f"<MealMenu(id={self.id}, date='{self.date}', type='{self.meal_type}')>"


class Holiday(Base):

    __tablename__ = "holidays"
    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False, unique=True, index=True)
    name = Column(
        String(100), nullable=True, comment="Название праздника (необязательно)"
    )
    created_at = Column(DateTime(timezone=True), server_default=UTC_NOW, nullable=False)

    def __repr__(self):
        return f"<Holiday(id={self.id}, date='{self.date}', name='{self.name}')>"


class NotificationAudience(str, enum.Enum):
    ALL = "all"
    PARENTS = "parents"
    TEACHERS = "teachers"


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(BigInteger, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)

    author_id = Column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    is_event = Column(Boolean, default=False, nullable=False)
    event_date = Column(DateTime(timezone=True), nullable=True)

    audience = Column(
        String(50), default=NotificationAudience.ALL.value, nullable=False, index=True
    )

    created_at = Column(DateTime(timezone=True), server_default=UTC_NOW, nullable=False)
    # updated_at = Column(DateTime(timezone=True),server_default=UTC_NOW,onupdate=UTC_NOW,nullable=False,)

    author = relationship("User", back_populates="notifications_authored")

    __table_args__ = (
        CheckConstraint(
            audience.in_([aud.value for aud in NotificationAudience]),
            name="notification_audience_check",
        ),
    )

    def __repr__(self):
        return f"<Notification(id={self.id}, title='{self.title[:20]}...', is_event={self.is_event})>"


class MonthlyCharge(Base):
    __tablename__ = "monthly_charges"

    id = Column(BigInteger, primary_key=True)
    child_id = Column(
        BigInteger,
        ForeignKey("children.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    year = Column(Integer, nullable=False, index=True)
    month = Column(Integer, nullable=False, index=True)
    amount_due = Column(Numeric(10, 2), nullable=False)
    calculation_details = Column(Text, nullable=True)

    calculated_at = Column(
        DateTime(timezone=True), server_default=UTC_NOW, nullable=False
    )

    child = relationship("Child", back_populates="monthly_charges")

    __table_args__ = (
        UniqueConstraint("child_id", "year", "month", name="uq_child_monthly_charge"),
        CheckConstraint("month >= 1 AND month <= 12", name="check_charge_month_range"),
        Index("ix_monthly_charges_child_year_month", "child_id", "year", "month"),
    )

    def __repr__(self):
        return f"<MonthlyCharge(id={self.id}, child_id={self.child_id}, year={self.year}, month={self.month}, amount={self.amount_due})>"
