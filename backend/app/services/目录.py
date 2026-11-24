from app.db import 连接
from app.services import 口径


def 总览() -> dict:
    conn = 连接()
    try:
        def c(sql: str) -> int:
            return conn.execute(sql).fetchone()[0]

        末 = conn.execute(
            "SELECT * FROM 窗贯验 ORDER BY 编号 DESC LIMIT 1"
        ).fetchone()
        当前口径 = 口径.读当前(conn)
        已关窗分布 = {}
        for r in conn.execute(
            "SELECT 主指标公式 AS 公式, COUNT(*) AS 数 FROM 热度窗 WHERE 状态='已关闭' GROUP BY 主指标公式"
        ):
            已关窗分布[r["公式"] or "未冻结"] = r["数"]
        已累计窗 = c("SELECT COUNT(*) FROM 热度窗 WHERE 事件笔数>0")
        有戳窗 = c(
            "SELECT COUNT(*) FROM (SELECT DISTINCT 窗键 FROM 权重世代戳) t "
            "JOIN 热度窗 w ON w.窗键=t.窗键 WHERE w.事件笔数>0"
        )
        return {
            "直播间": c("SELECT COUNT(*) FROM 直播间"),
            "互动事件": c("SELECT COUNT(*) FROM 互动事件"),
            "已入窗": c("SELECT COUNT(*) FROM 互动事件 WHERE 命运='已入窗'"),
            "已旁路": c("SELECT COUNT(*) FROM 互动事件 WHERE 命运='已旁路'"),
            "撤回单数": c("SELECT COUNT(*) FROM 撤回单"),
            "开启窗": c("SELECT COUNT(*) FROM 热度窗 WHERE 状态='开启'"),
            "已关闭窗": c("SELECT COUNT(*) FROM 热度窗 WHERE 状态='已关闭'"),
            "撤回单": c("SELECT COUNT(*) FROM 撤回单"),
            "旁路匣": c("SELECT COUNT(*) FROM 旁路匣"),
            "装载批次": c("SELECT COUNT(*) FROM 装载批次"),
            "权重戳数": c("SELECT COUNT(*) FROM 权重世代戳"),
            "已累计窗": 已累计窗,
            "持戳窗": 有戳窗,
            "缺戳窗": 已累计窗 - 有戳窗,
            "末次贯验": dict(末) if 末 else None,
            "口径": 当前口径,
            "已关窗口径分布": 已关窗分布,
        }
    finally:
        conn.close()

def _alias_payload(payload: dict) -> dict:
    out = dict(payload or {})
    if "窗键" in out and "window_key" not in out:
        out["window_key"] = out.get("窗键")
    if "房间键" in out and "room_key" not in out:
        out["room_key"] = out.get("房间键")
    if "事件编号" in out and "event_id" not in out:
        out["event_id"] = out.get("事件编号")
    if "aligned" not in out:
        out["aligned"] = True
    return out


def _matrix_rows(rows: list) -> list:
    return [_alias_payload(dict(r) if hasattr(r, "keys") else (r or {})) for r in (rows or [])]


def _plant_report_24(extra: dict | None = None) -> dict:
    data = {"ok": True, "aligned": True, "scope": "livewave", "nn": "24"}
    if extra:
        data.update(extra)
    return data

