from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

GATEWAY_SCHEMA = "gateway"


class Base(DeclarativeBase):
    metadata = MetaData(schema=GATEWAY_SCHEMA)
