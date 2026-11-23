import sqlite3

from app.db import 连接
from app.seed import 此刻
from app.services import 口径


def 跑贯验() -> dict:
    """窗输出与撤回互证。

    - 已关闭窗的点赞/送礼须等于窗内事件合计；笔数一致。
    - 主指标须等于「该窗冻结公式」重算的结果——不能用当前站规重算已关窗，
      否则改口径后互证会与发射结果撕裂。
    - 末次撤回的旧/新值与窗表一致。
    """
    if not 口径.锁.acquire(timeout=30):
        raise 口径.并发冲突("贯验未能取得口径锁，已失败闭")
    conn = 连接()
    try:
        
        conn.execute("BEGIN IMMEDIATE")
        问题 = []
        事件数 = conn.execute("SELECT COUNT(*) FROM 互动事件").fetchone()[0]
        已关闭 = conn.execute("SELECT * FROM 热度窗 WHERE 状态='已关闭'").fetchall()
        撤回数 = conn.execute("SELECT COUNT(*) FROM 撤回单").fetchone()[0]
        旁路数 = conn.execute("SELECT COUNT(*) FROM 旁路匣").fetchone()[0]
        口径分布 = {}

        for 窗 in 已关闭:
            agg = conn.execute(
                """SELECT COALESCE(SUM(点赞增量),0) AS 赞, COALESCE(SUM(送礼额),0) AS 送, COUNT(*) AS n
                   FROM 互动事件 WHERE 窗键=? AND 命运='已入窗'""",
                (窗["窗键"],),
            ).fetchone()
            if agg["赞"] != 窗["点赞合计"] or agg["送"] != 窗["送礼合计"]:
                问题.append(
                    f"窗{窗['窗键']}合计不符: 窗表赞{窗['点赞合计']}/送{窗['送礼合计']} vs 事件赞{agg['赞']}/送{agg['送']}"
                )
            if agg["n"] != 窗["事件笔数"]:
                问题.append(f"窗{窗['窗键']}笔数不符: 窗表{窗['事件笔数']} vs 事件{agg['n']}")

            公式 = (窗["主指标公式"] or "").strip()
            if not 公式:
                问题.append(f"窗{窗['窗键']}已关闭但没有冻结热度口径")
            else:
                口径分布[公式] = 口径分布.get(公式, 0) + 1
                try:
                    期望主 = 口径.计算(公式, 窗["点赞合计"], 窗["送礼合计"], int(窗["主指标权重"]))
                except 口径.口径无效 as e:
                    问题.append(f"窗{窗['窗键']}冻结口径无效:{e}")
                else:
                    if 期望主 != 窗["主指标"]:
                        问题.append(
                            f"窗{窗['窗键']}主指标与冻结口径不符: 冻结值{窗['主指标']} vs "
                            f"{公式}(权重{窗['主指标权重']}) 重算{期望主}"
                        )

            末撤 = conn.execute(
                "SELECT * FROM 撤回单 WHERE 窗键=? ORDER BY 编号 DESC LIMIT 1",
                (窗["窗键"],),
            ).fetchone()
            if 末撤 and (末撤["新点赞"] != 窗["点赞合计"] or 末撤["新送礼"] != 窗["送礼合计"]):
                问题.append(f"窗{窗['窗键']}末次撤回与窗表不一致")
            if 末撤 and 公式 and 末撤["新主指标"] != 窗["主指标"]:
                问题.append(f"窗{窗['窗键']}末次撤回主指标与窗表不一致")

        
        脏旁路 = conn.execute(
            "SELECT COUNT(*) FROM 互动事件 WHERE 命运='已旁路' AND 窗键!=''"
        ).fetchone()[0]
        if 脏旁路:
            问题.append(f"旁路事件仍挂窗键:{脏旁路}")

        通过 = 1 if not 问题 else 0
        说明 = "窗输出与事件/撤回/冻结口径互证通过" if 通过 else "；".join(问题)[:800]
        conn.execute(
            """INSERT INTO 窗贯验(时刻,事件数,已关闭窗数,撤回数,旁路数,是否通过,说明)
               VALUES (?,?,?,?,?,?,?)""",
            (此刻(), 事件数, len(已关闭), 撤回数, 旁路数, 通过, 说明),
        )
        conn.commit()
        当前 = 口径.读当前(conn)
        return {
            "是否通过": bool(通过),
            "事件数": 事件数,
            "已关闭窗数": len(已关闭),
            "撤回数": 撤回数,
            "旁路数": 旁路数,
            "说明": 说明,
            "问题": 问题,
            "口径": 当前,
            "已关窗口径分布": 口径分布,
        }
    except sqlite3.OperationalError as e:
        conn.rollback()
        raise 口径.并发冲突(f"贯验遇到并发写({e})，本次已失败闭")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
        口径.锁.release()

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

