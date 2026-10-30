"""Revocaciones persistentes de tokens de acceso hasta su vencimiento."""

from sqlalchemy import BigInteger, Column, String

from app.core.base_datos import Base


class TokenRevocado(Base):
    """Guarda la huella de la firma, nunca el JWT que permite autenticarse."""

    __tablename__ = "tokens_revocados"

    huella = Column(String(64), primary_key=True)
    expira_en = Column(BigInteger, nullable=False, index=True)
