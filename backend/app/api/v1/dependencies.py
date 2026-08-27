import hashlib
import hmac

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import get_db
from app.db.models import Employee


def get_current_employee(
    db: Session = Depends(get_db),
    development_user: str | None = Header(default=None, alias="X-Development-User"),
    wecom_userid: str | None = Header(default=None, alias="X-WeCom-UserId"),
    wecom_signature: str | None = Header(default=None, alias="X-WeCom-Auth-Signature"),
) -> Employee:
    """Resolve a development user locally or a signed identity injected by the SSO proxy."""
    if settings.environment == "development":
        employee_code = development_user or settings.development_default_user
        employee = db.scalar(select(Employee).where(Employee.employee_code == employee_code, Employee.is_active.is_(True)))
    else:
        if not settings.wecom_auth_proxy_token:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="生产环境尚未配置企业微信身份认证代理")
        if not wecom_userid or not wecom_signature:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少企业微信身份凭证")
        expected = hmac.new(settings.wecom_auth_proxy_token.encode(), wecom_userid.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(wecom_signature, expected):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="企业微信身份凭证无效")
        employee = db.scalar(select(Employee).where(Employee.wecom_userid == wecom_userid, Employee.is_active.is_(True)))
    if employee is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未知或已停用的企业微信身份")
    return employee


def require_roles(*roles: str):
    def dependency(employee: Employee = Depends(get_current_employee)) -> Employee:
        if employee.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="当前身份无此操作权限")
        return employee

    return dependency
