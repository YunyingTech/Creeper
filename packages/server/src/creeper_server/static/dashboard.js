"use strict";
const byId = (id) => document.getElementById(id);
let offset = 0;
let query = "";
let total = 0;
const limit = 25;
let busy = false;
function controls() {
  byId("previous").disabled = busy || offset === 0;
  byId("next").disabled = busy || offset + limit >= total;
  byId("refresh").disabled = busy;
  byId("search-form").querySelector("button").disabled = busy;
}
async function getJson(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error("数据读取失败，请确认服务已启动后重试。");
  return response.json();
}
function renderRows(items) {
  byId("rows").replaceChildren();
  for (const item of items) {
    const row = document.createElement("tr");
    const content = document.createElement("td");
    content.textContent = item.content;
    const source = document.createElement("td");
    source.textContent = item.collection || "未分类";
    try {
      const url = new URL(item.url);
      if (["http:", "https:"].includes(url.protocol)) {
        const link = document.createElement("a");
        link.href = url.href;
        link.textContent = url.hostname;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        source.append(link);
      }
    } catch { /* Old records may not have a URL. */ }
    const date = document.createElement("td");
    date.textContent = item.date || "未知时间";
    row.append(content, source, date);
    byId("rows").append(row);
  }
}
async function load() {
  if (busy) return;
  busy = true;
  controls();
  byId("message").className = "";
  byId("message").textContent = "正在读取采集结果…";
  try {
    const params = new URLSearchParams({limit, offset, q: query});
    const [results, stats] = await Promise.all([getJson(`/api/results?${params}`), getJson("/api/stats")]);
    total = results.total;
    renderRows(results.items);
    byId("records").textContent = stats.records.toLocaleString("zh-CN");
    byId("sources").textContent = stats.sources.toLocaleString("zh-CN");
    byId("latest").textContent = stats.latest || "暂无记录";
    byId("message").textContent = total ? `共 ${total.toLocaleString("zh-CN")} 条${query ? "匹配" : "采集"}内容` : (query ? "没有匹配内容，试试其他关键词。" : "还没有采集结果。运行一次采集后，在这里刷新查看。");
    byId("page-info").textContent = `第 ${Math.floor(offset / limit) + 1} / ${Math.max(1, Math.ceil(total / limit))} 页`;
  } catch (error) {
    byId("message").className = "error";
    byId("message").textContent = error.message;
    byId("rows").replaceChildren();
    total = 0;
  } finally {
    busy = false;
    controls();
  }
}
byId("refresh").addEventListener("click", () => load());
byId("search-form").addEventListener("submit", (event) => {
  event.preventDefault();
  if (busy) return;
  query = byId("query").value.trim();
  offset = 0;
  load();
});
byId("previous").addEventListener("click", () => { offset = Math.max(0, offset - limit); load(); });
byId("next").addEventListener("click", () => { offset += limit; load(); });
load();
