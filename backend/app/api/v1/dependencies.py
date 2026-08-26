from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import get_db
from app.db.models import Employee


def get_current_employee(
    db: Session = Depends(get_db),
    development_user: str | None = Header(default=None, alias="X-Development-User"),
) -> Employee:
    """Development adapter; replace this resolver with validated WeCom identity in production."""
    if settings.environment != "development":
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="生产环境尚未配置企业微信身份验证适配器")
    employee_code = development_user or settings.development_default_user
    employee = db.scalar(select(Employee).where(Employee.employee_code == employee_code, Employee.is_active.is_(True)))
    if employee is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未知或已停用的开发身份")
    return employee


def require_roles(*roles: str):
    def dependency(employee: Employee = Depends(get_current_employee)) -> Employee:
        if employee.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="当前身份无此操作权限")
        return employee

    return dependency
