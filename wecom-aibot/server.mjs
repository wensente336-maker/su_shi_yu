import http from "node:http";
import AiBot from "@wecom/aibot-node-sdk";

const { WECOM_AIBOT_BOT_ID: botId, WECOM_AIBOT_SECRET: secret, WECOM_AIBOT_INTERNAL_TOKEN: token } = process.env;
if (!botId || !secret || !token) throw new Error("缺少智能机器人必要配置");

let authenticated = false;
const client = new AiBot.WSClient({
  botId,
  secret,
  logger: { debug: () => {}, info: console.log, warn: console.warn, error: console.error },
});
client.on("authenticated", () => { authenticated = true; console.log("企业微信智能机器人已认证"); });
client.connect();
const ready = () => authenticated && client.isConnected;

const json = (response, status, data) => {
  response.writeHead(status, { "content-type": "application/json" });
  response.end(JSON.stringify(data));
};

http.createServer(async (request, response) => {
  if (request.method === "GET" && request.url === "/health") return json(response, ready() ? 200 : 503, { status: ready() ? "ok" : "connecting" });
  if (request.method !== "POST" || request.url !== "/send") return json(response, 404, { detail: "not found" });
  if (request.headers.authorization !== `Bearer ${token}`) return json(response, 401, { detail: "unauthorized" });
  let raw = "";
  request.on("data", (chunk) => { raw += chunk; });
  request.on("end", async () => {
    try {
      const { target_userid: targetUserid, content } = JSON.parse(raw);
      if (!ready()) return json(response, 503, { detail: "机器人尚未完成认证" });
      if (!targetUserid || !content) return json(response, 422, { detail: "缺少推送目标或内容" });
      await client.sendMessage(targetUserid, { msgtype: "markdown", markdown: { content } });
      return json(response, 200, { status: "sent" });
    } catch (error) {
      return json(response, 502, { detail: String(error.message || error) });
    }
  });
}).listen(8090, "0.0.0.0", () => console.log("智能机器人发送服务已启动"));
