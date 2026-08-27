"use client";

import { FormEvent, useEffect, useState } from "react";
import styles from "./page.module.css";

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8100";
type Week = { week_start: string; week_end: string };
type Target = { id: number; target_month: string; sales_person: string; sales_amount_target: number; signed_customers_target: number | null };
type Draft = { sales_person: string; sales_amount_target: string; signed_customers_target: string };
const blankDraft: Draft = { sales_person: "", sales_amount_target: "", signed_customers_target: "" };

export default function TargetsPage() {
  const [month, setMonth] = useState("");
  const [targets, setTargets] = useState<Target[]>([]);
  const [draft, setDraft] = useState<Draft>(blankDraft);
  const [status, setStatus] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetch(`${apiBase}/api/v1/reporting-weeks/current`)
      .then((response) => response.json())
      .then((week: Week) => setMonth(week.week_end.slice(0, 7)))
      .catch(() => setStatus("无法读取当前统计周期，请确认管理端服务可用。"));
  }, []);

  useEffect(() => {
    if (!month) return;
    fetch(`${apiBase}/api/v1/personal-monthly-targets?target_month=${month}`)
      .then((response) => response.ok ? response.json() : Promise.reject())
      .then((items: Target[]) => setTargets(items))
      .catch(() => setStatus("无法读取个人月度目标，请确认管理权限。"));
  }, [month]);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setStatus("");
    try {
      const response = await fetch(`${apiBase}/api/v1/personal-monthly-targets`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          target_month: month,
          sales_person: draft.sales_person,
          sales_amount_target: Number(draft.sales_amount_target),
          signed_customers_target: draft.signed_customers_target ? Number(draft.signed_customers_target) : null,
        }),
      });
      if (!response.ok) throw new Error();
      const saved: Target = await response.json();
      setTargets((current) => [...current.filter((item) => item.sales_person !== saved.sales_person), saved].sort((a, b) => a.sales_person.localeCompare(b.sales_person, "zh-CN")));
      setDraft(blankDraft);
      setStatus(`${saved.sales_person} 的 ${month} 月度目标已保存，看板会自动按当月累计计算完成率。`);
    } catch {
      setStatus("保存失败，请检查姓名、目标金额及管理权限。");
    } finally {
      setSaving(false);
    }
  }

  function edit(target: Target) {
    setDraft({
      sales_person: target.sales_person,
      sales_amount_target: String(target.sales_amount_target),
      signed_customers_target: target.signed_customers_target === null ? "" : String(target.signed_customers_target),
    });
    setStatus(`正在更新 ${target.sales_person} 的 ${month} 月度目标。`);
  }

  return <main className={styles.page}>
    <section className={styles.shell}>
      <a className={styles.back} href="/dashboard">← 返回经营数据中心</a>
      <header>
        <p>MANAGER CONFIGURATION</p>
        <h1>个人月度目标配置</h1>
        <span>{month ? `${month}｜按自然月保存，完成率按当月累计销售额计算` : "正在读取当前统计周期…"}</span>
      </header>
      <div className={styles.notice}>仅管理人员配置。姓名必须与销售周度经营数据中的 Sales（业务人员）一致；Sales Team 直接读取填报数据，不需重复维护。</div>
      <form className={styles.form} onSubmit={save}>
        <label>目标月份<input type="month" required value={month} onChange={(event) => setMonth(event.target.value)} /></label>
        <label>姓名（业务人员）<input required maxLength={100} value={draft.sales_person} onChange={(event) => setDraft((current) => ({ ...current, sales_person: event.target.value }))} placeholder="例如：陈蓉" /></label>
        <label>月度销售额目标（人民币/元）<input required type="number" min="1" step="10000" value={draft.sales_amount_target} onChange={(event) => setDraft((current) => ({ ...current, sales_amount_target: event.target.value }))} placeholder="例如：1500000" /></label>
        <label>月度成交客户目标（个，可选）<input type="number" min="0" step="1" value={draft.signed_customers_target} onChange={(event) => setDraft((current) => ({ ...current, signed_customers_target: event.target.value }))} placeholder="例如：15" /></label>
        <button disabled={!month || saving} type="submit">{saving ? "保存中…" : "保存个人月度目标"}</button>
      </form>
      <section className={styles.saved}>
        <h2>{month || "本月"} 已配置目标</h2>
        {targets.length ? <div className={styles.list}>{targets.map((target) => <article key={target.id}><div><b>{target.sales_person}</b><span>{target.sales_amount_target.toLocaleString("zh-CN")} 元{target.signed_customers_target !== null ? ` · 成交目标 ${target.signed_customers_target} 个` : ""}</span></div><button type="button" onClick={() => edit(target)}>编辑</button></article>)}</div> : <p>暂未配置个人月度目标。</p>}
      </section>
      {status && <p className={styles.status}>{status}</p>}
    </section>
  </main>;
}
