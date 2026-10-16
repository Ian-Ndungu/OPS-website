from sqlalchemy import LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column
from ..db import Base


class PublicImage(Base):
    __tablename__ = "public_images"
    path: Mapped[str] = mapped_column(String(255), primary_key=True)
    content_type: Mapped[str] = mapped_column(String(32))
    data: Mapped[bytes] = mapped_column(LargeBinary)
