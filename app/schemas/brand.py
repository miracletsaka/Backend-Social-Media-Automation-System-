from pydantic import BaseModel

class BrandCreate(BaseModel):
    id: str
    display_name: str
    is_active: bool = True

class BrandUpdate(BaseModel):
    display_name: str | None = None
    is_active: bool | None = None

class BrandOut(BaseModel):
    id: str
    display_name: str
    is_active: bool

    class Config:
        from_attributes = True
