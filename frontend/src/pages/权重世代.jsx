import React, { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { 取 } from "../api.js";

export default function 权重世代页() {
  const [数, 设] = useState(null);
  const [错, 设错] = useState("");
  const [窗键, 设窗键] = useState("");
  const 刷 = useCallback(() => {
    设错("");
    取("/核证/权重世代" + (窗键 ? `?窗键=${encodeURIComponent(窗键)}` : ""))
      .then(设)
      .catch((e) => 设错(String(e.message || e)));
  }, [窗键]);
  useEffect(() => { 刷(); }, [刷]);

  return (
    <div>
      <h1 className="题">权重世代核证</h1>
      <p className="述">
        只读核证：每一笔加权入窗都打一枚<strong>权重世代戳</strong>（窗键、权重值、公式版本、累计主指标、戳号）。
        本设计取舍为 <strong>入窗戳冻结发射</strong>——关窗发射与迟到修正只认戳内累计主指标，
        <strong>现行权重不得回溯已累计</strong>。
      </p>
      <div className="提示条">
        戳内累计须等于窗行主指标；窗行公式/权重/口径版本须与最新一枚戳同世代，否则互证
        <Link to="/窗互证"> 窗互证 </Link>会判撕裂。缺戳窗禁止发射/修正。
      </div>
      <div className="行">
        <input
          value={窗键}
          onChange={(e) => 设窗键(e.target.value)}
          placeholder="窗键（留空=全部）"
          style={{ minWidth: "18rem", padding: "0.35rem", background: "var(--块)", color: "var(--字)", border: "1px solid var(--线)", borderRadius: 4 }}
        />
        <button className="水" onClick={刷}>刷新</button>
      </div>
      {错 && <pre className="码">{错}</pre>}
      {数 && (
        <>
          <div className="格">
            <div className="卡"><b>{数.戳数}</b><span>权重戳</span></div>
            <div className="卡"><b>{数.钉死窗数}</b><span>钉死窗</span></div>
            <div className="卡"><b>{数.已累计窗数}</b><span>已累计窗</span></div>
            <div className="卡">
              <b>{数.缺戳窗?.length || 0}</b><span>缺戳窗</span>
            </div>
          </div>
          <div className={`提示条`}>
            采信现行权重：<b>{数.采信现行权重 ? "是（异常：应为否）" : "否"}</b> · 钉死：
            <b>{数.钉死 ? "全部一致" : "存在缺戳/分叉"}</b> · 设计取舍：{数.设计取舍}
          </div>

          <div className="段">
            <div className="段题">窗世代一致性</div>
            {!数.一致性?.length ? (
              <div className="空态">尚无已累计的热度窗</div>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>窗键</th><th>状态</th><th>窗行主指标</th><th>戳内累计</th>
                    <th>世代</th><th>戳号</th><th>一致</th>
                  </tr>
                </thead>
                <tbody>
                  {数.一致性.map((r) => (
                    <tr key={r.窗键}>
                      <td className="码">{r.窗键}</td><td>{r.状态}</td>
                      <td>{r.窗行主指标}</td><td><b>{r.戳内累计}</b></td>
                      <td className="码">{r.公式}(×{r.权重}) v{r.口径版本}</td>
                      <td className="码">{r.戳号}</td>
                      <td>
                        <span className={`徽章 ${r.一致 ? "通" : "败"}`}>{r.一致 ? "一致" : "分叉"}</span>
                        {r.错误 ? <div className="讯" style={{ margin: 0 }}>{r.错误}</div> : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {!!数.缺戳窗?.length && (
            <div className="段">
              <div className="段题">缺戳窗（禁止发射/修正）</div>
              <table>
                <thead><tr><th>窗键</th><th>状态</th><th>窗行主指标</th><th>原因</th></tr></thead>
                <tbody>
                  {数.缺戳窗.map((r) => (
                    <tr key={r.窗键}>
                      <td className="码">{r.窗键}</td><td>{r.状态}</td>
                      <td>{r.窗行主指标}</td><td>{r.原因}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="段">
            <div className="段题">权重戳明细（最近 200 枚）</div>
            {!数.权重戳?.length ? (
              <div className="空态">尚无权重戳</div>
            ) : (
              <table>
                <thead>
                  <tr><th>编号</th><th>窗键</th><th>权重值</th><th>公式版本</th><th>累计主指标</th><th>戳号</th><th>时刻</th></tr>
                </thead>
                <tbody>
                  {数.权重戳.map((r) => (
                    <tr key={r.编号}>
                      <td>{r.编号}</td><td className="码">{r.窗键}</td>
                      <td>{r.权重值}</td><td className="码">{r.公式版本}</td>
                      <td><b>{r.累计主指标}</b></td><td className="码">{r.戳号}</td>
                      <td className="码">{r.时刻}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}
    </div>
  );
}
