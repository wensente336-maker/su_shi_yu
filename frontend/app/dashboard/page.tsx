"use client";

import { useEffect, useState } from "react";

type Overview = {
  title: string;
  week: { week_start: string; week_end: string };
  metrics: { key: string; label: string; value: number; unit: string }[];
  submission_count: number;
  collection: { complete: boolean; required_form_count: number; submitted_form_count: number; missing_forms: string[] };
  analysis: { status: string; output?: string; review_comment?: string } | null;
  report_snapshot: { source_kind: string } | null;
};

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8100";

export default function DashboardPage() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch(`${apiBase}/api/v1/dashboard/overview`).then(async (response) => response.ok ? response.json() : Promise.reject()).then(setOverview).catch(() => setError("无法加载经营数据中心，请确认具备管理权限且后端服务可用。"));
  }, []);

  if (error) return <main style={{ fontFamily: "system-ui, sans-serif", margin: "3rem auto", maxWidth: 900, padding: "0 1rem" }}><h1>深圳盈进经营数据中心</h1><p>{error}</p></main>;
  if (!overview) return <main style={{ fontFamily: "system-ui, sans-serif", margin: "3rem auto", maxWidth: 900, padding: "0 1rem" }}>正在加载深圳盈进经营数据中心…</main>;

  return <main style={{ fontFamily: "system-ui, sans-serif", margin: "3rem auto", maxWidth: 900, padding: "0 1rem" }}>
    <h1>{overview.title}</h1>
    <p>统计周期：{overview.week.week_start} 至 {overview.week.week_end}</p>
    <section style={{ padding: "1rem", borderRadius: 10, background: overview.collection.complete ? "#ecfdf3" : "#fff8e8" }}>
      <strong>{overview.collection.complete ? "数据已收齐" : "等待数据收齐"}</strong>
      <p>已收齐 {overview.collection.submitted_form_count}/{overview.collection.required_form_count} 类经营表单。{overview.collection.missing_forms.length ? `待提交：${overview.collection.missing_forms.join("、")}` : ""}</p>
    </section>
    <section style={{ margin: "1.5rem 0", display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 12 }}>
      {overview.metrics.map((metric) => <div key={metric.key} style={{ background: "#f4f7fb", padding: 16, borderRadius: 10 }}><small>{metric.label}</small><br /><strong>{metric.value.toLocaleString("zh-CN")} {metric.unit}</strong></div>)}
    </section>
    <p>已提交表单：{overview.submission_count} 份；周报来源：{overview.report_snapshot?.source_kind ?? "未读取"}</p>
    <section style={{ padding: "1rem", border: "1px solid #e5e7eb", borderRadius: 10 }}><h2>经营分析</h2><p>状态：{overview.analysis?.status ?? "未生成"}</p><p style={{ whiteSpace: "pre-wrap" }}>{overview.analysis?.output ?? "数据收齐并生成、审核分析后将在此呈现。"}</p></section>
  </main>;
}
