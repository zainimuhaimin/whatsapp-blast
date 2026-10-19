# Skema Pydantic umum.
from pydantic import BaseModel, ConfigDict


class PageMeta(BaseModel):
    page: int
    limit: int
    total: int
    pages: int
