"""Standard page-based pagination for list endpoints."""

from dataclasses import dataclass

from fastapi import Query
from pydantic import BaseModel

MAX_PAGE_SIZE = 100


@dataclass(frozen=True)
class PageParams:
    page: int
    page_size: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def page_params(
    page: int = Query(1, ge=1, le=10_000),
    page_size: int = Query(25, ge=1, le=MAX_PAGE_SIZE),
) -> PageParams:
    return PageParams(page=page, page_size=page_size)


class Page[T](BaseModel):
    items: list[T]
    page: int
    page_size: int
    total: int
