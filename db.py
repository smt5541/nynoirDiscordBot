from sqlalchemy import create_engine

from config import DB_DIALECT, DB_USER, DB_PASS, DB_HOST, DB_NAME


def get_engine():
    engine = create_engine(f"{DB_DIALECT}{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}?charset=utf8mb4")
    return engine
