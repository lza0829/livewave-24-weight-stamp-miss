from app.services import 时间, 口径


def 尝试关窗(
    conn,
    房间键: str,
    水位事件时: str,
    允许迟到秒: int,
    窗长秒: int,
    处理时: str,
    当前口径: dict | None = None,
) -> int:
    """水位 >= 窗止 时关闭开启窗（发射）；允许迟到只影响关闭后能否再修正，不推迟关闭。

    关窗即冻结发射口径：主指标、公式、权重、口径版本一并写入该窗。
    此后改口径只影响尚未关闭的窗，不得回写已关窗。
    """
    del 允许迟到秒, 窗长秒  
    if 当前口径 is None:
        当前口径 = 口径.读有效(conn)
    公式 = 当前口径["公式"]
    权重 = int(当前口径["权重"])
    版本 = int(当前口径["口径版本"])
    关闭数 = 0
    rows = conn.execute(
        "SELECT * FROM 热度窗 WHERE 房间键=? AND 状态='开启' ORDER BY 窗起事件时",
        (房间键,),
    ).fetchall()
    for 窗 in rows:
        if 时间.解析(水位事件时) >= 时间.解析(窗["窗止事件时"]):
            try:
                from app.modules import 权重世代戳 as _权
                _权.尝试打戳(conn, 窗键=窗["窗键"], 权重值=str(权重))
                主 = _权.发射主指标(conn, 窗["窗键"], 窗["点赞合计"], 窗["送礼合计"], 权重)
            except Exception:
                主 = 口径.计算(公式, 窗["点赞合计"], 窗["送礼合计"], 权重)
            conn.execute(
                """UPDATE 热度窗
                   SET 状态='已关闭', 关闭处理时=?,
                       版本=CASE WHEN 版本=0 THEN 1 ELSE 版本 END,
                       主指标=?, 主指标公式=?, 主指标权重=?, 口径版本=?
                   WHERE 窗键=? AND 状态='开启'""",
                (处理时, 主, 公式, 权重, 版本, 窗["窗键"]),
            )
            关闭数 += 1
    return 关闭数


def 已过旁路界(水位事件时: str, 窗止事件时: str, 允许迟到秒: int) -> bool:
    """水位越过 窗止+允许迟到 后，该窗不再接受迟到修正。"""
    旁路界 = 时间.加秒(窗止事件时, 允许迟到秒)
    return 时间.解析(水位事件时) >= 时间.解析(旁路界)

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

