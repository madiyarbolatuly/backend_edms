from typing import List
from uuid import UUID

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import http_409, http_404
from app.db.repositories.auth.auth import AuthRepository
from app.db.tables.base_class import NotifyEnum
from app.schemas.auth.bands import TokenData
from app.db.tables.documents.notify import Notify
from app.schemas.documents.bands import Notification, NotifyPatchStatus

class NotifyRepo:

    def __init__(self, session: AsyncSession ) -> None:
        self.session = session

    async def notify(
        self,
        user: TokenData,
        receivers: List[str],
        filename: str,
        auth_repo: AuthRepository,
    ) -> None:
        """
        Notify users about a shared file.

        Args:
            user (TokenData): The authenticated user who shared the file.
            receivers (List[str]): The list of email addresses of the users to be notified.
            filename (str): The name of the shared file.
            auth_repo (AuthRepository): The repository for accessing user authentication data.

        Returns:
            None

        Raises:
            HTTP_500: If an error occurs while adding the notification entry.
        """

        for receiver in receivers:
            receiver_details = await auth_repo.get_user(field="email", detail=receiver)
            if receiver_details is None:
                # Was raised from inside a bare `except Exception`, so a genuine
                # database error also reported "the user does not exist".
                raise http_404(
                    msg=f"Пользователь {receiver} не найден — у него нет аккаунта в docflow."
                )

            notify_entry = Notify(
                # The column is `user_id`; `receiver_id=` raised TypeError, so
                # no notification was ever written.
                user_id=receiver_details.id,
                message=f"{user.username} shared {filename} with you! Access the shared file via mail...",
                # `type` is NOT NULL with no default. It holds the same enum as
                # `status` and nothing reads it — it looks vestigial — but the
                # insert fails without it.
                type=NotifyEnum.unread,
                status=NotifyEnum.unread,
            )
            self.session.add(notify_entry)

        # One flush for the whole batch; the request's session commits. Committing
        # per receiver left some users notified and others not when one failed.
        await self.session.flush()

    async def get_notification_by_id(self, n_id: UUID, user: TokenData) -> Notification:
        """
        Get a notification by its ID for a specific user.

        Args:
            n_id (UUID): The ID of the notification.
            user (TokenData): The authenticated user.

        Returns:
            Notification: The notification object.

        Raises:
            HTTP_404: If no notification with the given ID is found.
        """

        # Chained `.where(...)`, never `a and b`: Python's `and` returns its
        # right operand, so the user filter was silently discarded and this
        # matched every notification with that id — and once a user had two
        # rows, `scalar_one_or_none()` raised MultipleResultsFound, which the
        # bare `except` below turned into a misleading 404.
        stmt = (
            select(Notify)
            .where(Notify.user_id == user.id)
            .where(Notify.id == n_id)
        )

        result = (await self.session.execute(stmt)).scalar_one_or_none()
        if result is None:
            raise http_404(msg=f"No notification with id: {n_id}")
        return Notification.model_validate(result, from_attributes=True)

    async def get_notifications(
        self, user: TokenData, limit: int = 200
    ) -> List[Notification]:
        """
        Get notifications for a specific user, newest first.

        Args:
            user (TokenData): The authenticated user.
            limit (int): Most recent N. The bell only ever shows a handful.

        Returns:
            List[Notification]: A list of notification objects.
        """

        # Newest first, and bounded. Unordered and unlimited, this returned a
        # user's whole history in whatever order the plan produced.
        stmt = (
            select(Notify)
            .where(Notify.user_id == user.id)
            .order_by(Notify.created_at.desc(), Notify.id)
            .limit(limit)
        )

        rows = (await self.session.execute(stmt)).scalars().all()

        return [Notification.model_validate(row, from_attributes=True) for row in rows]

    async def mark_all_read(self, user: TokenData) -> List[Notification]:
        """
        Mark all notifications as read for a specific user.

        Args:
            user (TokenData): The authenticated user.

        Returns:
            List[Notification]: A list of notification objects that have been marked as read.

        Raises:
            HTTP_409: If an error occurs while updating the notification status.
        """

        stmt = (
            update(Notify)
            .where(Notify.user_id == user.id)
            .where(Notify.status != NotifyEnum.read)
            .values({Notify.status: NotifyEnum.read})
        )

        try:
            await self.session.execute(stmt)
            await self.session.flush()
            return await self.get_notifications(user=user)
        except Exception as e:
            raise http_409(msg="Error updating marking notification read...") from e

    async def update_status(
        self, n_id: UUID, updated_status: NotifyPatchStatus, user: TokenData
    ):
        """
        Update the status of a notification for a specific user.

        Args:
            n_id (UUID): The ID of the notification to update.
            updated_status (NotifyPatchStatus): The updated status for the notification.
            user (TokenData): The authenticated user.

        Returns:
            Notification: The updated notification object.

        Raises:
            HTTP_409: If an error occurs while updating the notification status.
        """
        # The worst instance of the `and` bug: `a and b and c` evaluates to `c`,
        # so this filtered on the *status* alone and rewrote every notification
        # belonging to every user. Updating one row is the entire point.
        stmt = (
            update(Notify)
            .where(Notify.user_id == user.id)
            .where(Notify.id == n_id)
            .where(Notify.status != updated_status.status)
            .values({Notify.status: updated_status.status})
        )

        try:
            await self.session.execute(stmt)
            await self.session.flush()
            return await self.get_notification_by_id(n_id=n_id, user=user)
        except Exception as e:
            raise http_409(msg="Error updating notification status...") from e

    async def clear_notification(self, user: TokenData) -> None:
        """
        Clear all notifications for a specific user.

        Args:
            user (TokenData): The authenticated user.

        Returns:
            None

        Raises:
            Exception: If an error occurs while clearing the notifications.
        """

        stmt = delete(Notify).where(Notify.user_id == user.id)

        try:
            await self.session.execute(stmt)
        except Exception as e:
            raise e
