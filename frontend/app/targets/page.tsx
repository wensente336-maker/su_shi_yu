"use client";

import { FormEvent, useEffect, useState } from "react";
import styles from "./page.module.css";

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8100";
const teams = ["海外留学", "香港保险", "身份规划"];
type Week = { week_start: string; week_end: string };
type Target = { id: number; target_month: string; sales_person: string; sales_amount_target: number; signed_customers_target: number | null };
type SalesPerson = { id: number; name: string; sales_team: string };
type TargetDraft = { sales_person: string; sales_amount_target: string; signed_customers_target: string };
const blankTarget: TargetDraft = { sales_person: "", sales_amount_target: "", signed_customers_target: "" };

export default function TargetsPage() {
  const [month, setMonth] = useState("");
  const [targets, setTargets] = useState<Target[]>([]);
  const [salesPeople, setSalesPeople] = useState<SalesPerson[]>([]);
  const [targetDraft, setTargetDraft] = useState<TargetDraft>(blankTarget);
  const [personName, setPersonName] = useState("");
  const [personTeam, setPersonTeam] = useState(teams[0]);
  const [status, setStatus] = useState("");
  const [saving, setSaving] = useState(false);
  const [savingPerson, setSavingPerson] = useState(false);

  function loadSalesPeople() {
    return fetch(`${apiBase}/api/v1/sales-people`)
      .then((response) => response.ok ? response.json() : Promise.reject())
      .then((items: SalesPerson[]) => setSalesPeople(items));
  }

  useEffect(() => {
    Promise.all([
      fetch(`${apiBase}/api/v1/reporting-weeks/current`).then((response) => response.json()),
      loadSalesPeople(),
    ])
      .then(([week]) => setMonth((week as Week).week_end.slice(0, 7)))
      .catch(() => setStatus("无法读取管理配置，请确认服务及管理权限。"));
  }, []);

  useEffect(() => {
    if (!month) return;
    fetch(`${apiBase}/api/v1/personal-monthly-targets?target_month=${month}`)
      .then((response) => response.ok ? response.json() : Promise.reject())
      .then((items: Target[]) => setTargets(items))
      .catch(() => setStatus("无法读取个人月度目标，请确认管理权限。"));
  }, [month]);

  async function saveTarget(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setStatus("");
    try {
      const response = await fetch(`${apiBase}/api/v1/personal-monthly-targets`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          target_month: month,
          sales_person: targetDraft.sales_person,
          sales_amount_target: Number(targetDraft.sales_amount_target),
          signed_customers_target: targetDraft.signed_customers_target ? Number(targetDraft.signed_customers_target) : null,
        }),
      });
      if (!response.ok) throw new Error();
      const saved: Target = await response.json();
      setTargets((current) => [...current.filter((item) => item.sales_person !== saved.sales_person), saved].sort((a, b) => a.sales_person.localeCompare(b.sales_person, "zh-CN")));
      setTargetDraft(blankTarget);
      setStatus(`${saved.sales_person} 的 ${month} 月度目标已保存。`);
    } catch {
      setStatus("保存失败，请选择业务人员并检查目标金额。");
    } finally {
      setSaving(false);
    }
  }

  async function saveSalesPerson(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSavingPerson(true);
    setStatus("");
    try {
      const response = await fetch(`${apiBase}/api/v1/sales-people`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ name: personName, sales_team: personTeam }),
      });
      if (!response.ok) throw new Error();
      await loadSalesPeople();
      setPersonName("");
      setStatus("业务人员名单已保存；该人员现在可用于经营数据填报与月度目标配置。");
    } catch {
      setStatus("保存业务人员失败，请检查姓名、团队及管理权限。");
    } finally {
      setSavingPerson(false);
    }
  }

  function edit(target: Target) {
    setTargetDraft({ sales_person: target.sales_person, sales_amount_target: String(target.sales_amount_target), signed_customers_target: target.signed_customers_target === null ? "" : String(target.signed_customers_target) });
    setStatus(`正在更新 ${target.sales_person} 的 ${month} 月度目标。`);
  }

  return <main className={styles.page}>
    <section className={styles.shell}>
      <a className={styles.back} href="/dashboard">← 返回经营数据中心</a>
      <header><p>MANAGER CONFIGURATION</p><h1>个人月度目标配置</h1><span>{month ? `${month}｜按自然月保存，完成率按当月累计销售额计算` : "正在读取当前统计周期…"}</span></header>
      <div className={styles.notice}>先维护统一业务人员名单，再设置个人月度目标。经营数据填报只能选择名单内人员，团队归属会自动带出，避免姓名与团队口径不一致。</div>
      <section className={styles.saved}>
        <h2>业务人员名单</h2>
        <form className={styles.form} onSubmit={saveSalesPerson}>
          <label>姓名（业务人员）<input required maxLength={100} value={personName} onChange={(event) => setPersonName(event.target.value)} placeholder="例如：陈蓉" /></label>
          <label>Sales Team<select value={personTeam} onChange={(event) => setPersonTeam(event.target.value)}>{teams.map((team) => <option key={team}>{team}</option>)}</select></label>
          <button disabled={savingPerson} type="submit">{savingPerson ? "保存中…" : "新增或更新人员"}</button>
        </form>
        {salesPeople.length ? <div className={styles.list}>{salesPeople.map((person) => <article key={person.id}><div><b>{person.name}</b><span>{person.sales_team}</span></div><button type="button" onClick={() => { setPersonName(person.name); setPersonTeam(person.sales_team); }}>编辑归属</button></article>)}</div> : <p>暂无业务人员，请先新增。</p>}
      </section>
      <section className={styles.saved}>
        <h2>设置个人月度目标</h2>
        <form className={styles.form} onSubmit={saveTarget}>
          <label>目标月份<input type="month" required value={month} onChange={(event) => setMonth(event.target.value)} /></label>
          <label>姓名（业务人员）<select required value={targetDraft.sales_person} onChange={(event) => setTargetDraft((current) => ({ ...current, sales_person: event.target.value }))}><option value="">请选择业务人员</option>{salesPeople.map((person) => <option key={person.id} value={person.name}>{person.name}｜{person.sales_team}</option>)}</select></label>
          <label>月度销售额目标（人民币/元）<input required type="number" min="1" step="10000" value={targetDraft.sales_amount_target} onChange={(event) => setTargetDraft((current) => ({ ...current, sales_amount_target: event.target.value }))} placeholder="例如：1500000" /></label>
          <label>月度成交客户目标（个，可选）<input type="number" min="0" step="1" value={targetDraft.signed_customers_target} onChange={(event) => setTargetDraft((current) => ({ ...current, signed_customers_target: event.target.value }))} placeholder="例如：15" /></label>
          <button disabled={!month || saving} type="submit">{saving ? "保存中…" : "保存个人月度目标"}</button>
        </form>
        <div className={styles.list}>{targets.length ? targets.map((target) => <article key={target.id}><div><b>{target.sales_person}</b><span>{target.sales_amount_target.toLocaleString("zh-CN")} 元{target.signed_customers_target !== null ? ` · 成交目标 ${target.signed_customers_target} 个` : ""}</span></div><button type="button" onClick={() => edit(target)}>编辑</button></article>) : <p>该月份暂未配置个人月度目标。</p>}</div>
      </section>
      {status && <p className={styles.status}>{status}</p>}
    </section>
  </main>;
}
