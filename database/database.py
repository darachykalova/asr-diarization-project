import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://asr_user:asr_password@localhost:5432/asr_db"
)

engine = create_engine(
    DATABASE_URL,
    echo=False
)

Base = declarative_base()