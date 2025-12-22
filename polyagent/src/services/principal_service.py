from uuid import UUID

from src.database import SessionLocal
from src.models import Principal


class PrincipalService:
    def __init__(self) -> None:
        pass

    def get_principals(self, principal_type: str | None = None) -> list[Principal]:
        """Get all principals, optionally filtered by type."""
        session = SessionLocal()
        try:
            query = session.query(Principal)
            if principal_type is not None:
                query = query.filter(Principal.principal_type == principal_type)
            principals = query.all()
            for principal in principals:
                session.refresh(principal)
                session.expunge(principal)
            return principals
        finally:
            session.close()

    def get_principal(self, principal_id: UUID | str) -> Principal | None:
        """Get a specific principal by ID."""
        session = SessionLocal()
        try:
            principal = session.query(Principal).filter(Principal.id == principal_id).first()
            if principal:
                session.refresh(principal)
                session.expunge(principal)
            return principal
        finally:
            session.close()
