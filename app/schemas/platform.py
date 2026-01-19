from pydantic import BaseModel

class PlatformCreate(BaseModel):
    id: str
    display_name: str
    is_active: bool = True

class PlatformUpdate(BaseModel):
    display_name: str | None = None
    is_active: bool | None = None

class PlatformOut(BaseModel):
    id: str
    display_name: str
    is_active: bool

    class Config:
        from_attributes = True
