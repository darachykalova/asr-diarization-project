from database.database import Base, engine
from database import models


def init_db() -> None:
    Base.metadata.create_all(bind=engine)