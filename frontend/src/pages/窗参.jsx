import React, { useEffect, useState } from "react";
import { 取, 递 } from "../api.js";

export default function 窗参页() {
  const [规, 设规] = useState(null);
  const [桩, 设桩] = useState([]);
  const [口径, 设口径] = useState(null);
  const [变更, 设变更] = useState([]);
  const [公式, 设公式] = useState("");
  const [权重, 设权重] = useState(0);
  const [讯, 设讯] = useState("");

  const 刷口径 = () =>
    Promise.all([
      取("/热度口径").then((d) => {
        设口径(d);
        设公式(d.公式);
        设权重(d.权重);
      }),
      取("/热度口径/变更").then(设变更),
    ]);

  useEffect(() => {
    取("/站规").then(设规);
    取("/空桩").then(设桩);
    刷口径();
  }, []);

  if (!规) return <p className="讯">加载中…</p>;
  const 主参 = ["窗长秒", "允许迟到秒", "关窗条件", "旁路条件", "水位推进策略"];

  const 提交 = async () => {
    设讯("");
    try {
      const r = await 递("/热度口径", {
        公式,
        权重: Number(权重),
        期望版本: 口径 ? 口径.口径版本 : undefined,
      });
      设讯(`已提交：${r.变更说明}（口径版本 ${r.口径版本}）`);
      刷口径();
    } catch (e) {
      设讯(`未提交：${String(e.message || e)}`);
    }
  };

  return (
    <div>
      <h1 className="题">窗参</h1>
      <p className="述">窗长、允许迟到、关窗/旁路条件与<strong>热度口径</strong>。邻题空桩挂在这里，不参与主链。</p>

      {口径 && (
        <div className="段">
          <div className="段题">热度口径（全局单选）</div>
          <div className="提示条">
            当前：<b>{口径.公式}</b>（权重 {口径.权重}） · 主指标 = <span className="码">{口径.主指标 || "—"}</span> ·{" "}
            口径版本 {口径.口径版本} · {口径.valid ? "有效" : "无效（装载将失败闭）"}
          </div>
          <div className="行">
            {(口径.可选公式 || []).map((f) => (
              <button key={f} className={`次 ${公式 === f ? "亮片" : ""}`} onClick={() => 设公式(f)}>
                {f}
              </button>
            ))}
            <span className="讯" style={{ margin: 0 }}>送礼权重</span>
            <input
              type="number"
              min="0"
              step="1"
              value={权重}
              onChange={(e) => 设权重(e.target.value)}
              style={{ width: "6rem", padding: "0.35rem", background: "var(--块)", color: "var(--字)", border: "1px solid var(--线)", borderRadius: 4 }}
            />
            <button className="水" onClick={提交}>提交口径</button>
          </div>
          <p className="述" style={{ marginTop: 0 }}>
            改口径只影响之后关闭的窗；<strong>已关窗发射结果不变</strong>。与装载/关窗并发时本次变更失败闭，不半截提交。
          </p>
          {讯 && <div className="报箱">{讯}</div>}
          <div className="段题">口径变更履历</div>
          {!变更.length ? (
            <div className="空态">尚无口径变更</div>
          ) : (
            <table>
              <thead>
                <tr><th>编号</th><th>时刻</th><th>旧</th><th>新</th><th>版本</th><th>说明</th></tr>
              </thead>
              <tbody>
                {变更.map((r) => (
                  <tr key={r.编号}>
                    <td>{r.编号}</td><td className="码">{r.时刻}</td>
                    <td>{r.旧公式}(×{r.旧权重})</td><td>{r.新公式}(×{r.新权重})</td>
                    <td>{r.旧版本} → {r.新版本}</td><td>{r.说明}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      <div className="段">
        <div className="段题">主链参数</div>
        <table>
          <thead><tr><th>键</th><th>值</th></tr></thead>
          <tbody>
            {主参.filter((k) => 规[k] != null).map((k) => (
              <tr key={k}><td>{k}</td><td className="码">{规[k]}</td></tr>
            ))}
            {Object.entries(规)
              .filter(([k]) => !主参.includes(k) && !["热度公式", "送礼权重", "口径版本"].includes(k))
              .map(([k, v]) => (
                <tr key={k}><td>{k}</td><td className="码">{v}</td></tr>
              ))}
          </tbody>
        </table>
      </div>
      <div className="段">
        <div className="段题">邻题空桩</div>
        <table>
          <thead><tr><th>名</th><th>状态</th></tr></thead>
          <tbody>{桩.map((p) => <tr key={p.名}><td>{p.名}</td><td>{p.状态}</td></tr>)}</tbody>
        </table>
      </div>
    </div>
  );
}
