from typing import Generic, TypeVar, Optional
from pydantic import BaseModel


# Define a type variable to allow generic responses
T = TypeVar("T")


class StandardResponse(BaseModel, Generic[T]):
    data: Optional[T]  # Optional to handle cases where there's no data
    message: Optional[str]
    status: str
