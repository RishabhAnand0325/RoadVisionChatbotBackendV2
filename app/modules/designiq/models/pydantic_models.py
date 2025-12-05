from pydantic import BaseModel

class DesignIQResponse(BaseModel):
    message: str
    status: str
