import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# 1) Load the .env file sitting next to this module
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

# 2) Fetch the DATABASE_URL (will raise if missing)
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL not set")

# 3) Set up SQLAlchemy engine & session factory
engine = create_engine(DATABASE_URL, connect_args={} if "sqlite" not in DATABASE_URL else {"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 4) Base class for your models
Base = declarative_base()

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
