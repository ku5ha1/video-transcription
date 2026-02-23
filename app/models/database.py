from sqlalchemy import (
    Column,
    String,
    Boolean,
    DateTime,
    Float,
    Integer,
    ForeignKey,
    Enum as SQLEnum,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime
import uuid
import enum

Base = declarative_base()


class VideoStatus(str, enum.Enum):
    """Video processing status enum"""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ChatRole(str, enum.Enum):
    """Chat message role enum"""

    USER = "user"
    ASSISTANT = "assistant"


class User(Base):
    """User model for authentication and multi-tenancy"""

    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    videos = relationship("Video", back_populates="user", cascade="all, delete-orphan")
    transcript_segments = relationship(
        "TranscriptSegment", back_populates="user", cascade="all, delete-orphan"
    )
    chat_messages = relationship(
        "ChatMessage", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<User(id={self.id}, email={self.email})>"


class Video(Base):
    """Video model for tracking uploaded videos and processing status"""

    __tablename__ = "videos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    filename = Column(String(255), nullable=False)
    minio_object_key = Column(String(500), nullable=False)
    file_hash = Column(
        String(64), nullable=True, index=True
    )  # SHA-256 hash for deduplication
    status = Column(
        SQLEnum(VideoStatus), default=VideoStatus.PENDING, nullable=False, index=True
    )
    duration = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    user = relationship("User", back_populates="videos")
    transcript_segments = relationship(
        "TranscriptSegment", back_populates="video", cascade="all, delete-orphan"
    )
    chat_messages = relationship(
        "ChatMessage", back_populates="video", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Video(id={self.id}, filename={self.filename}, status={self.status})>"


class TranscriptSegment(Base):
    """Transcript segment model for storing transcription results"""

    __tablename__ = "transcript_segments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    video_id = Column(
        UUID(as_uuid=True),
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    start_time = Column(Float, nullable=False)
    end_time = Column(Float, nullable=False)
    speaker_label = Column(String(50), nullable=False)
    text = Column(Text, nullable=False)
    audio_emotion = Column(String(50), nullable=True)
    text_tone = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    video = relationship("Video", back_populates="transcript_segments")
    user = relationship("User", back_populates="transcript_segments")

    def __repr__(self):
        return f"<TranscriptSegment(id={self.id}, video_id={self.video_id}, speaker={self.speaker_label})>"


class ChatMessage(Base):
    """Chat message model for storing conversation history"""

    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    video_id = Column(
        UUID(as_uuid=True),
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(String(50), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    video = relationship("Video", back_populates="chat_messages")
    user = relationship("User", back_populates="chat_messages")

    def __repr__(self):
        return (
            f"<ChatMessage(id={self.id}, video_id={self.video_id}, role={self.role})>"
        )
