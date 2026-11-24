import React, { useEffect, useState } from "react";
import { 取 } from "../api.js";

export default function 热度窗页() {
  const [窗, 设] = useState([]);
  const [口径, 设口径] = useState(null);
  const [滤, 设滤] = useState("");
  const 刷 = () =>
    Promise.all([
      取("/热度窗" + (滤 ? `?状态=${encodeURIComponent(滤)}` : "")).then(设),
      取("/热度口径").then(设口径),
    ]);
  useEffect(() => { 刷(); }, [滤]);
  return (
    <div>
      <h1 className="题">③ 热度窗</h1>
      <p className="述">
        按事件时翻滚对齐的热度窗。<strong>主指标</strong>按全局选定口径计：金额加权 = 点赞 + 送礼×权重，等权计数 = 点赞（送礼只旁路展示）。
        每笔入窗按<strong>当时权重世代</strong>累进并打钉；关窗发射取戳内累计，之后改口径不会回溯已累计，
        已关闭窗显示冻结的世代（公式/权重/口径版本）。
      </p>
      {口径 && (
        <div className="提示条">
          当前口径：<b>{口径.公式}</b>（权重 {口径.权重}） · 主指标 = <span className="码">{口径.主指标 || "—"}</span>{" "}
          · 口径版本 {口径.口径版本} · {口径.valid ? "有效" : "无效（装载将失败闭）"}
        </div>
      )}
      <div className="行">
        {["", "开启", "已关闭"].map((s) => (
          <button key={s || "全"} className={`次 ${滤 === s ? "亮片" : ""}`} onClick={() => 设滤(s)}>
            {s || "全部"}
          </button>
        ))}
        <button className="次" onClick={刷}>刷新窗</button>
      </div>
      {!窗.length ? (
        <div className="空态">暂无热度窗。先去事件流推准时样例。</div>
      ) : (
        <table>
          <thead>
            <tr>
              <th>窗键</th><th>房间</th><th>窗起</th><th>窗止</th><th>状态</th>
              <th>点赞合计</th><th>送礼合计</th><th>主指标</th><th>口径</th>
              <th>笔数</th><th>版本</th><th>关闭处理时</th>
            </tr>
          </thead>
          <tbody>
            {窗.map((r) => (
              <tr key={r.窗键}>
                <td className="码">{r.窗键}</td><td>{r.房间键}</td>
                <td className="码">{r.窗起事件时}</td><td className="码">{r.窗止事件时}</td>
                <td>{r.状态}</td><td>{r.点赞合计}</td><td>{r.送礼合计}</td>
                <td>
                  <b>{r.主指标}</b>
                  {r.主指标零因 ? <div className="讯" style={{ margin: 0 }}>{r.主指标零因}</div> : null}
                </td>
                <td>
                  <span className="码">{r.公式}(×{r.权重})</span>
                  {r.冻结 ? <div className="讯" style={{ margin: 0 }}>已冻结 v{r.口径版本}</div> : null}
                </td>
                <td>{r.事件笔数}</td><td>{r.版本}</td>
                <td className="码">{r.关闭处理时 || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
