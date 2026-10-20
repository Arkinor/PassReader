"""
Pydantic модели для API менеджера паролей.
"""

from typing import Optional

from pydantic import BaseModel, Field


class PasswordItem(BaseModel):
    """Модель записи пароля."""
    name: str = Field(..., description="Название/описание записи")
    login: str = Field(..., description="Логин")
    password: str = Field(..., description="Пароль")
    email: Optional[str] = Field(None, description="Электронная почта")
    comment: Optional[str] = None
    group: Optional[str] = Field(None, description="Группа записи (опционально)")


class PasswordDelete(BaseModel):
    """Модель для удаления записи по индексу."""
    index: int
