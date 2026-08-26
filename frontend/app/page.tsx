"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

type FormField = { key: string; label: string; type: string; required: boolean; config: Record<string, unknown> };
type FormSchema = { code: string; name: string; description?: string; department: string; fields?: FormField[] };
type Week = { id: number; week_start: string; week_end: string; status: string; is_current: boolean };
type Overview = { metrics: { key: string; label: string; value: number; unit: string }[]; submission_count: number; analysis: { status: string; output?: string } | null; report_snapshot: { source_kind: string } | null };

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8100";

export default function HomePage() {
  const [schemas, setSchemas] = useState<FormSchema[]>([]);
  const [selected, setSelected] = useState<FormSchema | null>(null);
  const [week, setWeek] = useState<Week | null>(null);
  const [values, setValues] = useState<Record<string, string>>({});
  const [message, setMessage] = useState("正在加载可用表单…");
  const [overview, setOverview] = useState<Overview | null>(null);

  useEffect(() => {
    Promise.all([fetch(`${apiBase}/api/v1/form-schemas`).then((r) => r.json()), fetch(`${apiBase}/api/v1/reporting-weeks/current`).then((r) => r.json())])
      .then(([items, currentWeek]) => {
        setSchemas(items);
        setWeek(currentWeek);
        if (items[0]) setSelected(items[0]);
        setMessage("");
      })
      .catch(() => setMessage("无法连接经营数据服务，请确认后端已启动。"));
  }, []);

  useEffect(() => {
    fetch(`${apiBase}/api/v1/dashboard/overview`).then((response) => response.ok ? response.json() : null).then(setOverview).catch(() => setOverview(null));
  }, []);

  useEffect(() => {
    if (!selected) return;
    fetch(`${apiBase}/api/v1/form-schemas/${selected.code}`)
      .then((r) => r.json())
      .then((schema) => {
        setSelected(schema);
        setValues({});
      });
  }, [selected?.code]);

  const period = useMemo(() => week ? `${week.week_start} 至 ${week.week_end}` : "", [week]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!selected || !week) return;
    const typedValues: Record<string, string | number> = {};
    for (const field of selected.fields ?? []) {
      const value = values[field.key] ?? "";
      typedValues[field.key] = field.type === "currency" || field.type === "number" ? Number(value) : value;
    }
    const response = await fetch(`${apiBase}/api/v1/form-schemas/${selected.code}/submissions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reporting_week_id: week.id, values: typedValues }),
    });
    const result = await response.json();
    setMessage(response.ok ? "已保存本周数据；再次提交会更新同一份记录。" : result.detail ?? "提交失败");
  }

  return <main style={{ fontFamily: "system-ui, sans-serif", margin: "3rem auto", maxWidth: 760, padding: "0 1rem" }}>
    <h1>公司经营数据中心</h1>
    <p>当前统计周：{period || "加载中"}</p>
    {overview && <section style={{ margin: "1.5rem 0", padding: "1rem", background: "#f4f7fb", borderRadius: 10 }}>
      <h2 style={{ marginTop: 0 }}>经营驾驶舱</h2>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))", gap: 10 }}>
        {overview.metrics.map((metric) => <div key={metric.key} style={{ background: "white", padding: 12, borderRadius: 8 }}><small>{metric.label}</small><br /><strong>{metric.value.toLocaleString("zh-CN")} {metric.unit}</strong></div>)}
      </div>
      <p>已提交表单：{overview.submission_count} 份；周报来源：{overview.report_snapshot?.source_kind ?? "未读取"}；分析状态：{overview.analysis?.status ?? "未生成"}</p>
    </section>}
    <label>选择表单　
      <select value={selected?.code ?? ""} onChange={(e) => setSelected(schemas.find((item) => item.code === e.target.value) ?? null)}>
        {schemas.map((item) => <option key={item.code} value={item.code}>{item.name}</option>)}
      </select>
    </label>
    {selected?.fields && <form onSubmit={submit} style={{ display: "grid", gap: 16, marginTop: 24 }}>
      <h2>{selected.name}</h2>
      {selected.description && <p>{selected.description}</p>}
      {selected.fields.map((field) => <label key={field.key} style={{ display: "grid", gap: 6 }}>
        {field.label}{field.required ? " *" : ""}
        {field.type === "textarea" ? <textarea required={field.required} maxLength={Number(field.config.max_length) || undefined} value={values[field.key] ?? ""} onChange={(e) => setValues({ ...values, [field.key]: e.target.value })} rows={5} /> : field.type === "select" ? <select required={field.required} value={values[field.key] ?? ""} onChange={(e) => setValues({ ...values, [field.key]: e.target.value })}><option value="">请选择</option>{Array.isArray(field.config.options) && field.config.options.map((option) => <option key={String(option)} value={String(option)}>{String(option)}</option>)}</select> : <input required={field.required} maxLength={field.type === "text" ? Number(field.config.max_length) || undefined : undefined} min={typeof field.config.min === "number" ? field.config.min : undefined} step={field.type === "currency" ? "0.01" : "1"} type={field.type === "text" ? "text" : "number"} value={values[field.key] ?? ""} onChange={(e) => setValues({ ...values, [field.key]: e.target.value })} />}
      </label>)}
      <button type="submit" style={{ width: 140, padding: "0.6rem" }}>提交本周数据</button>
    </form>}
    {message && <p role="status">{message}</p>}
  </main>;
}
