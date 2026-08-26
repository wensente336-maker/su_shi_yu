"use client";

import { useEffect, useState } from "react";
import styles from "./page.module.css";

const teams = ["海外留学", "香港保险", "身份规划"];
const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8100";

type Week = { id: number; week_start: string; week_end: string };
type Target = { sales_team: string; sales_amount_target: number; signed_customers_target: number | null };

export default function TargetsPage() {
  const [week, setWeek] = useState<Week | null>(null);
  const [targets, setTargets] = useState<Record<string, Target>>({});
  const [status, setStatus] = useState("");
  const [saving, setSaving] = useState("");

  useEffect(() => {
    fetch(`${apiBase}/api/v1/reporting-weeks/current`)
      .then((response) => response.json())
      .then((currentWeek: Week) => {
        setWeek(currentWeek);
        return fetch(`${apiBase}/api/v1/team-weekly-targets?reporting_week_id=${currentWeek.id}`);
      })
      .then((response) => response.json())
      .then((items: Target[]) => setTargets(Object.fromEntries(items.map((item) => [item.sales_team, item]))))
      .catch(() => setStatus("无法读取团队目标配置，请确认管理端服务可用。"));
  }, []);

  async function save(team: string, form: HTMLFormElement) {
    if (!week) return;
    const values = new FormData(form);
    setSaving(team);
    setStatus("");
    try {
      const response = await fetch(`${apiBase}/api/v1/team-weekly-targets`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          reporting_week_id: week.id,
          sales_team: team,
          sales_amount_target: Number(values.get("sales_amount_target")),
          signed_customers_target: values.get("signed_customers_target") ? Number(values.get("signed_customers_target")) : null,
        }),
      });
      if (!response.ok) throw new Error();
      const item: Target = await response.json();
      setTargets((current) => ({ ...current, [team]: item }));
      setStatus(`${team}目标已保存，看板将自动更新完成率。`);
    } catch {
      setStatus("保存失败，请检查输入内容及管理权限。");
    } finally {
      setSaving("");
    }
  }

  return <main className={styles.page}>
    <section className={styles.shell}>
      <a className={styles.back} href="/dashboard">← 返回经营数据中心</a>
      <header>
        <p>MANAGER CONFIGURATION</p>
        <h1>团队周度目标配置</h1>
        <span>{week ? `${week.week_start} 至 ${week.week_end}` : "正在读取统计周期…"}</span>
      </header>
      <div className={styles.notice}>目标仅由管理人员配置；销售与财务填报人员无需重复填写。保存后会自动更新“团队目标进度”。</div>
      <div className={styles.grid}>
        {teams.map((team) => {
          const target = targets[team];
          return <form className={styles.card} key={team} onSubmit={(event) => { event.preventDefault(); save(team, event.currentTarget); }}>
            <h2>{team}</h2>
            <label>本周销售额目标（人民币/元）<input name="sales_amount_target" type="number" min="0" step="10000" required defaultValue={target?.sales_amount_target ?? ""} placeholder="例如 1500000" /></label>
            <label>成交客户目标（个，可选）<input name="signed_customers_target" type="number" min="0" step="1" defaultValue={target?.signed_customers_target ?? ""} placeholder="例如 15" /></label>
            <button disabled={!week || saving === team} type="submit">{saving === team ? "保存中…" : "保存团队目标"}</button>
          </form>;
        })}
      </div>
      {status && <p className={styles.status}>{status}</p>}
    </section>
  </main>;
}
