from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Department, Employee, FormField, FormSchema, ReportingWeek


def seed_reference_data(db: Session) -> None:
    if not db.scalar(select(Department.id).limit(1)):
        finance = Department(code="finance", name="财务部")
        sales = Department(code="sales", name="销售部")
        db.add_all([finance, sales])
        db.flush()
        db.add_all([
            Employee(employee_code="admin", name="系统管理员", role="admin"),
            Employee(employee_code="finance_lead", name="财务负责人", department_id=finance.id, role="department_manager"),
            Employee(employee_code="sales_lead", name="销售负责人", department_id=sales.id, role="department_manager"),
            Employee(employee_code="sales_member", name="销售专员", department_id=sales.id, role="member"),
        ])
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        db.add(ReportingWeek(week_start=week_start, week_end=week_start + timedelta(days=6), is_current=True))
        finance_form = FormSchema(code="finance-weekly-v1", name="财务周度经营数据", department_id=finance.id, description="财务部每周经营关键数据", version=1)
        sales_form = FormSchema(code="sales-weekly-v1", name="销售周度经营数据", department_id=sales.id, description="销售部每周经营关键数据", version=2)
        db.add_all([finance_form, sales_form])
        db.flush()
        db.add_all([
        FormField(schema_id=finance_form.id, key="revenue", label="本周营业收入", field_type="currency", required=True, position=1, config={"min": 0, "unit": "元"}),
        FormField(schema_id=finance_form.id, key="cash_inflow", label="本周回款", field_type="currency", required=True, position=2, config={"min": 0, "unit": "元"}),
        FormField(schema_id=finance_form.id, key="notes", label="异常说明", field_type="textarea", required=False, position=3, config={"max_length": 1000}),
            FormField(schema_id=sales_form.id, key="sales_person", label="Sales", field_type="text", required=True, position=1, config={"max_length": 100}),
            FormField(schema_id=sales_form.id, key="sales_team", label="Sales Team", field_type="select", required=True, position=2, config={"options": ["海外留学", "香港保险", "身份规划"]}),
            FormField(schema_id=sales_form.id, key="sales_amount", label="本周销售额", field_type="currency", required=True, position=3, config={"min": 0, "unit": "元"}),
            FormField(schema_id=sales_form.id, key="new_leads", label="新增线索数", field_type="number", required=True, position=4, config={"min": 0, "step": 1}),
            FormField(schema_id=sales_form.id, key="signed_customers", label="成交客户数", field_type="number", required=True, position=5, config={"min": 0, "step": 1}),
            FormField(schema_id=sales_form.id, key="notes", label="业务说明", field_type="textarea", required=False, position=6, config={"max_length": 1000}),
        ])
        db.commit()

    _sync_sales_fields(db)


def _sync_sales_fields(db: Session) -> None:
    """Apply non-destructive system field additions to an already-initialized database."""
    form = db.scalar(select(FormSchema).where(FormSchema.code == "sales-weekly-v1"))
    if form is None:
        return
    required_fields = {
        "sales_person": {"label": "Sales", "field_type": "text", "required": True, "position": 1, "config": {"max_length": 100}},
        "sales_team": {"label": "Sales Team", "field_type": "select", "required": True, "position": 2, "config": {"options": ["海外留学", "香港保险", "身份规划"]}},
    }
    fields = {field.key: field for field in db.scalars(select(FormField).where(FormField.schema_id == form.id)).all()}
    for key, specification in required_fields.items():
        if key not in fields:
            db.add(FormField(schema_id=form.id, key=key, **specification))
    for key, position in {"sales_amount": 3, "new_leads": 4, "signed_customers": 5, "notes": 6}.items():
        if key in fields:
            fields[key].position = position
    form.version = max(form.version, 2)
    db.commit()
