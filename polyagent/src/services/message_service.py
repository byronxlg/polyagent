from datetime import datetime
from uuid import UUID

from src.database import SessionLocal
from src.models import Message, Principal


class MessageService:
    def __init__(self) -> None:
        pass

    def send_message(self, from_principal_id: UUID | str, to_principal_id: UUID | str, content: str) -> Message:
        session = SessionLocal()
        try:
            # Validate principals exist
            from_principal = session.query(Principal).filter(Principal.id == from_principal_id).first()
            if not from_principal:
                msg = f"Principal {from_principal_id} not found"
                raise ValueError(msg)

            to_principal = session.query(Principal).filter(Principal.id == to_principal_id).first()
            if not to_principal:
                msg = f"Principal {to_principal_id} not found"
                raise ValueError(msg)

            message = Message(
                from_principal_id=from_principal_id,
                to_principal_id=to_principal_id,
                content=content,
                sent_at=datetime.utcnow(),
            )
            session.add(message)
            session.commit()
            session.refresh(message)
            session.expunge(message)
            return message
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_inbox(self, principal_id: UUID | str) -> list[Message]:
        session = SessionLocal()
        try:
            # Validate principal exists
            principal = session.query(Principal).filter(Principal.id == principal_id).first()
            if not principal:
                msg = f"Principal {principal_id} not found"
                raise ValueError(msg)

            messages = (
                session.query(Message)
                .filter(Message.to_principal_id == principal_id, Message.received_at.is_(None))
                .all()
            )

            for message in messages:
                message.received_at = datetime.utcnow()

            session.commit()
            for message in messages:
                session.refresh(message)
                session.expunge(message)
            return messages
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
