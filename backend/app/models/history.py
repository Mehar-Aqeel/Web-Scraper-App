import time
from sqlalchemy import JSON, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.services.database import Base


class ScrapingJob(Base):
    __tablename__ = "scraping_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    fields: Mapped[str] = mapped_column(Text, nullable=False)   # comma-separated
    status: Mapped[str] = mapped_column(String(20), default="done")
    record_count: Mapped[int] = mapped_column(Integer, default=0)
    warning_count: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[float] = mapped_column(Float, default=time.time)
    used_js: Mapped[int] = mapped_column(Integer, default=0)    # 0/1 bool


class ScrapedRecord(Base):
    __tablename__ = "scraped_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=True)
    extra: Mapped[dict] = mapped_column(JSON, nullable=True)    # text, level, alt, etc.
    source_url: Mapped[str] = mapped_column(Text, nullable=True)
