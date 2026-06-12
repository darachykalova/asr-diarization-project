from sqlalchemy.orm import sessionmaker

from database.database import engine


SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)