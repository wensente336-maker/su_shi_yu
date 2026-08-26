"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import styles from "./page.module.css";

type FormField = { key: string; label: string; type: string; required: boolean; config: Record<string, unknown> };
type FormSchema = { code: string; name: string; description?: string; department: string; fields?: FormField[] };
type Week = { id: number; week_start: string; week_end: string };
const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8100";

export default function HomePage() {
  const [schemas, setSchemas] = useState<FormSchema[]>([]);
  const [selected, setSelected] = useState<FormSchema | null>(null);
  const [week, setWeek] = useState<Week | null>(null);
  const [values, setValues] = useState<Record<string, string>>({});
  const [message, setMessage] = useState("正在加载可用表单…");
  const [isSuccess, setIsSuccess] = useState(false);

  useEffect(() => {
    Promise.all([fetch(`${apiBase}/api/v1/form-schemas`).then((response) => response.json()), fetch(`${apiBase}/api/v1/reporting-weeks/current`).then((response) => response.json())])
      .then(([items, currentWeek]) => { setSchemas(items); setWeek(currentWeek); if (items[0]) setSelected(items[0]); setMessage(""); })
      .catch(() => setMessage("无法连接经营数据服务，请确认后端已启动。"));
  }, []);
  useEffect(() => {
    if (!selected) return;
    fetch(`${apiBase}/api/v1/form-schemas/${selected.code}`).then((response) => response.json()).then((schema) => { setSelected(schema); setValues({}); setIsSuccess(false); });
  }, [selected?.code]);

  const period = useMemo(() => week ? `${week.week_start} 至 ${week.week_end}` : "正在读取统计周期", [week]);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!selected || !week) return;
    const typedValues: Record<string, string | number> = {};
    for (const field of selected.fields ?? []) { const value = values[field.key] ?? ""; typedValues[field.key] = field.type === "currency" || field.type === "number" ? Number(value) : value; }
    const response = await fetch(`${apiBase}/api/v1/form-schemas/${selected.code}/submissions`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ reporting_week_id: week.id, values: typedValues }) });
    const result = await response.json(); setIsSuccess(response.ok); setMessage(response.ok ? "本周数据已保存，可再次提交更新本周数据。" : result.detail ?? "提交失败，请检查后重试。");
  }

  return <main className={styles.page}><div className={styles.shell}>
    <header className={styles.header}><div className={styles.brandRow}><div className={styles.brandMark}>YJ</div><div><p className={styles.brand}>深圳盈进</p><p className={styles.brandSub}>BUSINESS DATA</p></div><span className={styles.badge}>周度填报</span></div><h1>经营数据填报</h1><p className={styles.intro}>请完成本周经营数据填报。数据由后台统一汇总，本页面不展示经营结果。</p><div className={styles.period}><span className={styles.periodDot} />当前统计周期：{period}</div></header>
    <nav className={styles.tabs} aria-label="表单类型">{schemas.map((schema) => <button className={`${styles.tab} ${selected?.code === schema.code ? styles.activeTab : ""}`} type="button" key={schema.code} onClick={() => setSelected(schema)}>{schema.name}</button>)}</nav>
    <section className={styles.card}><div className={styles.cardHeading}><div><p className={styles.eyebrow}>{selected?.department === "sales" ? "SALES" : "FINANCE"}</p><h2>{selected?.name ?? "加载表单中"}</h2></div><span className={styles.requiredHint}><i /> 为必填项</span></div>{selected?.description && <p className={styles.description}>{selected.description}</p>}
      {selected?.fields && <form onSubmit={submit} className={styles.form}><div className={styles.fieldList}>{selected.fields.map((field) => <label key={field.key} className={styles.field}><span className={styles.label}>{field.label}{field.config.hint ? <em>（{String(field.config.hint)}）</em> : null}{field.required ? <b>*</b> : null}</span>{field.type === "textarea" ? <textarea className={styles.control} required={field.required} maxLength={Number(field.config.max_length) || undefined} value={values[field.key] ?? ""} onChange={(event) => setValues({ ...values, [field.key]: event.target.value })} placeholder="请补充本周业务说明、异常或风险" rows={5} /> : field.type === "select" ? <select className={styles.control} required={field.required} value={values[field.key] ?? ""} onChange={(event) => setValues({ ...values, [field.key]: event.target.value })}><option value="">请选择业务团队</option>{Array.isArray(field.config.options) && field.config.options.map((option) => <option key={String(option)} value={String(option)}>{String(option)}</option>)}</select> : <input className={styles.control} required={field.required} maxLength={field.type === "text" ? Number(field.config.max_length) || undefined : undefined} min={typeof field.config.min === "number" ? field.config.min : undefined} step={field.type === "currency" ? "0.01" : "1"} type={field.type === "text" ? "text" : "number"} value={values[field.key] ?? ""} onChange={(event) => setValues({ ...values, [field.key]: event.target.value })} placeholder={field.type === "text" ? "请输入姓名" : "请输入数值"} />}</label>)}</div><div className={styles.actionBar}><p>提交后自动保存至本周统计周期</p><button className={styles.submit} type="submit">提交本周数据 <span>→</span></button></div></form>}
    </section>{message && <div className={`${styles.message} ${isSuccess ? styles.success : styles.notice}`} role="status"><strong>{isSuccess ? "提交成功" : "提示"}</strong><span>{message}</span></div>}
  </div></main>;
}
