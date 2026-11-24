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

    发射写闸按**权重世代戳**取主指标 / 公式 / 权重 / 口径版本：
    - 有累计的窗，四件套全部来自同一枚最新戳，绝不按现行权重重算已累计；
    - 空窗（无累计、无戳）才按当前口径冻结，主指标 0；
    - 戳缺失或与窗行分叉时抛异常，由装载整票回滚，不留半截关窗。
    """
    del 允许迟到秒, 窗长秒
    if 当前口径 is None:
        当前口径 = 口径.读有效(conn)
    from app.modules import 权重世代戳 as _权

    关闭数 = 0
    rows = conn.execute(
        "SELECT * FROM 热度窗 WHERE 房间键=? AND 状态='开启' ORDER BY 窗起事件时",
        (房间键,),
    ).fetchall()
    for 窗 in rows:
        if 时间.解析(水位事件时) >= 时间.解析(窗["窗止事件时"]):
            _权.发射写闸(
                conn,
                窗键=窗["窗键"],
                处理时=处理时,
                当前口径=当前口径,
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
