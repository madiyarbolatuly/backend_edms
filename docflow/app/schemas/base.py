from pydantic import BaseModel

class BaseSchema(BaseModel):
    model_config = {
        "arbitrary_types_allowed": True,
        "from_attributes": True  # Это заменяет старый Config.from_attributes = True
    }
