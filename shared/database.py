from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from .config import db_url

class Base(DeclarativeBase):
    pass

def database(name: str):
    url = db_url(name)
    kwargs = {'connect_args': {'check_same_thread': False}} if url.startswith('sqlite') else {}
    engine = create_engine(url, pool_pre_ping=True, **kwargs)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
