"use client";

import { useEffect, useMemo, useState } from "react";
import styles from "./page.module.css";

type Metric = { key: string; label: string; value: number; unit: string };
type Team = { name: string; sales_amount: number; signed_customers: number };
type Person = { name: string; sales_team: string; sales_amount: number; signed_customers: number };
type Trend = { label: string; sales_amount: number; cash_inflow: number };
type PersonalGoal = { name: string; sales_team: string; sales_amount: number; signed_customers: number; sales_amount_target: number; signed_customers_target: number | null; sales_completion: number | null };
type Overview = {
  title: string;
  week: { week_start: string; week_end: string };
  metrics: Metric[];
  submission_count: number;
  collection: { complete: boolean; required_form_count: number; submitted_form_count: number; missing_forms: string[] };
  source_status: { name: string; complete: boolean }[];
  team_performance: Team[];
  sales_ranking: Person[];
  trend: Trend[];
  personal_goals: { target_month: string; configured: boolean; message: string; source_note: string; items: PersonalGoal[] };
  previous_week_report: { week_start: string; week_end: string; source_kind: string } | null;
  analysis: { status: string; output?: string; review_comment?: string } | null;
};

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8100";
const money = (value: number) => value >= 10000 ? `¥${(value / 10000).toFixed(1)}万` : `¥${value.toLocaleString("zh-CN")}`;

function LineChart({ data }: { data: Trend[] }) {
  const max = Math.max(...data.map((item) => Math.max(item.sales_amount, item.cash_inflow)), 1);
  const points = (key: "sales_amount" | "cash_inflow") => data.map((item, index) => `${data.length === 1 ? 50 : 8 + index * 84 / (data.length - 1)},${88 - item[key] / max * 72}`).join(" ");
  return <div className={styles.lineWrap}><svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-label="销售额与回款趋势图"><line x1="0" x2="100" y1="88" y2="88" className={styles.gridLine} /><line x1="0" x2="100" y1="52" y2="52" className={styles.gridLine} /><line x1="0" x2="100" y1="16" y2="16" className={styles.gridLine} /><polyline points={points("cash_inflow")} className={styles.cashLine} /><polyline points={points("sales_amount")} className={styles.salesLine} /></svg><div className={styles.chartLabels}>{data.map((item) => <span key={item.label}>{item.label}</span>)}</div></div>;
}

function extractSection(output: string | undefined, marker: string, fallback: string) {
  if (!output) return fallback;
  const start = output.indexOf(marker);
  if (start === -1) return fallback;
  const content = output.slice(start + marker.length).split(/\n##\s*\d+\./)[0];
  const firstLine = content.split("\n").map((line) => line.replace(/^[-*\s#]+/, "").replace(/\*\*/g, "").trim()).find(Boolean);
  return firstLine || fallback;
}

export default function DashboardPage() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [error, setError] = useState("");
  const [targetMonth, setTargetMonth] = useState("");
  const [showFullAnalysis, setShowFullAnalysis] = useState(false);

  useEffect(() => {
    const query = targetMonth ? `?target_month=${targetMonth}` : "";
    fetch(`${apiBase}/api/v1/dashboard/overview${query}`)
      .then((response) => response.ok ? response.json() : Promise.reject())
      .then((data: Overview) => { setOverview(data); if (!targetMonth) setTargetMonth(data.personal_goals.target_month); })
      .catch(() => setError("无法加载经营数据中心，请确认具备管理权限且后端服务可用。"));
  }, [targetMonth]);

  const teamMax = useMemo(() => Math.max(...(overview?.team_performance.map((item) => item.sales_amount) ?? []), 1), [overview]);
  if (error) return <main className={styles.page}><p className={styles.loadState}>{error}</p></main>;
  if (!overview) return <main className={styles.page}><p className={styles.loadState}>正在加载深圳盈进经营数据中心…</p></main>;

  const decisionItems = [
    { label: "经营结论", content: extractSection(overview.analysis?.output, "本周核心经营结论", "数据收齐后将生成本周经营结论。") },
    { label: "关键风险", content: extractSection(overview.analysis?.output, "风险与待核实事项", "请持续关注回款、收入确认与数据口径差异。") },
    { label: "下步行动", content: extractSection(overview.analysis?.output, "下周建议行动", "请根据本周团队与个人数据明确下周责任和行动。") },
  ];

  return <main className={styles.page}><div className={styles.shell}>
    <header className={styles.hero}>
      <div><p className={styles.kicker}>SHENZHEN YINGJIN · BUSINESS WAR ROOM</p><h1>{overview.title}</h1><p className={styles.period}>{overview.week.week_start} 至 {overview.week.week_end} · 本周经营战报</p></div>
      <div className={styles.heroActions}><a className={styles.targetLink} href="/targets">配置个人目标</a><div className={`${styles.readiness} ${overview.collection.complete ? styles.ready : styles.pending}`}><b>{overview.collection.complete ? "数据已收齐" : "等待收齐"}</b><span>{overview.collection.submitted_form_count}/{overview.collection.required_form_count} 类表单已提交</span></div></div>
    </header>

    {!overview.collection.complete && <section className={styles.warning}><strong>数据尚未收齐</strong><span>待提交：{overview.collection.missing_forms.join("、")}</span></section>}
    {!overview.collection.complete ? <section className={styles.gate}><p>RESULTS LOCKED</p><h2>等待全部经营数据收齐</h2><span>销售周度经营数据与财务周度经营数据提交完成后，将自动解锁经营结果、团队 PK、月度目标和 AI 分析。</span></section> : <>
      <section className={styles.metricRack}>{overview.metrics.map((metric, index) => <article className={`${styles.metric} ${index < 2 ? styles.priorityMetric : ""}`} key={metric.key}><p>{metric.label}</p><strong>{metric.unit === "元" ? money(metric.value) : `${metric.value.toLocaleString("zh-CN")} ${metric.unit}`}</strong><span>{index < 2 ? "本周核心指标" : "本周累计"}</span></article>)}</section>

      <section className={styles.grid}>
        <article className={`${styles.panel} ${styles.pkPanel}`}><div className={styles.panelHead}><div><p>TEAM BATTLE</p><h2>团队竞赛 PK</h2></div><span className={styles.pkTag}>以销售额为准</span></div>{overview.team_performance.length ? <div className={styles.bars}>{overview.team_performance.map((team, index) => <div className={styles.barRow} key={team.name}><div className={styles.barName}><b>#{index + 1}</b><span>{team.name}</span><strong>{money(team.sales_amount)}</strong></div><div className={styles.track}><div className={styles.bar} style={{ width: `${team.sales_amount / teamMax * 100}%` }} /></div><small>成交客户 {team.signed_customers} 个</small></div>)}</div> : <p className={styles.empty}>收集销售数据后显示团队竞赛。</p>}</article>

        <article className={`${styles.panel} ${styles.decisionPanel}`}><div className={styles.panelHead}><div><p>WEEKLY BRIEF</p><h2>本周需决策</h2></div><span className={styles.reviewTag}>{overview.analysis?.status ?? "未生成"}</span></div><div className={styles.decisions}>{decisionItems.map((item) => <section key={item.label}><b>{item.label}</b><p>{item.content}</p></section>)}</div><button className={styles.analysisButton} type="button" onClick={() => setShowFullAnalysis((current) => !current)}>{showFullAnalysis ? "收起完整 AI 分析" : "查看完整 AI 分析"}</button></article>

        <article className={`${styles.panel} ${styles.trendPanel}`}><div className={styles.panelHead}><div><p>WEEKLY TREND</p><h2>销售额与回款趋势</h2></div><div className={styles.legend}><span className={styles.salesLegend}>销售额</span><span className={styles.cashLegend}>回款</span></div></div>{overview.trend.length ? <LineChart data={overview.trend} /> : <p className={styles.empty}>尚无历史数据</p>}</article>

        <article className={`${styles.panel} ${styles.targetPanel}`}><div className={styles.panelHead}><div><p>PERSONAL GOAL PROGRESS</p><h2>个人月度目标进度</h2></div><input aria-label="目标月份" className={styles.targetMonth} type="month" value={targetMonth} onChange={(event) => setTargetMonth(event.target.value)} /></div>{overview.personal_goals.items.length ? <div className={styles.targetList}>{overview.personal_goals.items.map((item) => { const rate = item.sales_completion ?? 0; return <div className={styles.targetRow} key={item.name}><div><b>{item.name}</b><span>{item.sales_team} · 当月累计 {money(item.sales_amount)} / {money(item.sales_amount_target)}</span></div><strong className={rate < 1 ? styles.targetRisk : styles.targetHit}>{item.sales_completion === null ? "—" : `${Math.round(rate * 100)}%`}</strong><div className={styles.progress}><span className={rate < 1 ? styles.riskProgress : ""} style={{ width: `${Math.min(rate, 1) * 100}%` }} /></div></div>; })}</div> : <div className={styles.targetEmpty}><div className={styles.progress}><span /></div><p>{overview.personal_goals.message}</p><small>{overview.personal_goals.source_note}</small></div>}</article>

        <article className={`${styles.panel} ${styles.rankPanel}`}><div className={styles.panelHead}><div><p>SALES LEADERBOARD</p><h2>业务人员排行</h2></div><span className={styles.total}>{overview.sales_ranking.length} 人</span></div>{overview.sales_ranking.length ? <ol className={styles.ranking}>{overview.sales_ranking.map((person, index) => <li key={person.name}><b className={`${styles.rank} ${index < 3 ? styles[`rank${index + 1}`] : ""}`}>{index + 1}</b><div><strong>{person.name}</strong><span>{person.sales_team} · 成交 {person.signed_customers} 个</span></div><em>{money(person.sales_amount)}</em></li>)}</ol> : <p className={styles.empty}>收集销售数据后显示个人排行。</p>}</article>

        <article className={`${styles.panel} ${styles.sourcePanel}`}><div className={styles.panelHead}><div><p>DATA SOURCE</p><h2>数据收集状态</h2></div><span className={styles.total}>{overview.submission_count} 份</span></div><div className={styles.sources}>{overview.source_status.map((source) => <div key={source.name}><span>{source.name}</span><b className={source.complete ? styles.sourceDone : styles.sourceTodo}>{source.complete ? "已完成" : "待提交"}</b></div>)}</div></article>

        {showFullAnalysis && <article className={`${styles.panel} ${styles.fullAnalysisPanel}`}><div className={styles.panelHead}><div><p>AI BUSINESS REVIEW</p><h2>完整经营分析</h2></div><span className={styles.reviewTag}>{overview.analysis?.status ?? "未生成"}</span></div><div className={styles.analysisText}>{overview.analysis?.output ?? "数据收齐并完成 AI 分析、人工审核后，将在这里呈现完整分析。"}</div>{overview.previous_week_report && <p className={styles.priorReport}>已接入上周真实周报：{overview.previous_week_report.week_start} 至 {overview.previous_week_report.week_end}（仅作背景，不作为本周归因依据）</p>}{overview.analysis?.review_comment && <p className={styles.reviewComment}>审核意见：{overview.analysis.review_comment}</p>}</article>}
      </section>
    </>}
  </div></main>;
}
