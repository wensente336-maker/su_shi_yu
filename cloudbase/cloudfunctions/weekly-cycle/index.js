/**
 * CloudBase timer function. It only wakes the API; all business idempotency
 * remains in the backend's weekly run service.
 */
exports.main = async () => {
  const endpoint = process.env.WEEKLY_CYCLE_ENDPOINT;
  const token = process.env.CLOUDBASE_SCHEDULER_TOKEN;
  if (!endpoint || !token) {
    throw new Error("WEEKLY_CYCLE_ENDPOINT 或 CLOUDBASE_SCHEDULER_TOKEN 未配置");
  }

  const response = await fetch(endpoint, {
    method: "POST",
    headers: { "X-CloudBase-Scheduler-Token": token },
  });
  const body = await response.text();
  if (!response.ok) {
    throw new Error(`经营周报定时任务失败: HTTP ${response.status} ${body.slice(0, 500)}`);
  }
  return { ok: true, status: response.status, body: body.slice(0, 1_000) };
};
