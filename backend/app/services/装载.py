import json
import sqlite3
from app.db import 连接
from app.seed import 此刻
from app.services import 时间, 热度窗, 口径


def 装一批(体: dict) -> dict:
    """入流一批互动事件：推进水位线，尝试关窗，处理迟到/旁路/撤回。

    口径（类 Flink）：
    - 水位 = 已见最大事件时
    - 窗 [起,止) 在 水位>=止 时关闭发射
    - 关闭后至 水位>=止+允许迟到 仍可迟到修正并发撤回
    - 越过 止+允许迟到 则旁路

    热度口径：整批在锁内、单个事务内完成；加权入窗成功即写入权重世代戳。
    关窗发射 / 迟到修正只按戳内累计与冻结世代，绝不按现行权重重算已累计。
    站规口径无效、戳缺失/分叉或与改口径并发冲突时整体回滚（失败闭），不留半截。
    """
    批次编号 = 体.get("批次编号") or f"批-{此刻().replace(':', '').replace('-', '')}"
    事件列表 = 体.get("事件") or []
    if not 口径.锁.acquire(timeout=30):
        raise 口径.并发冲突("装载未能取得口径锁，已失败闭；本批未提交")
    conn = 连接()
    try:
        conn.execute("BEGIN IMMEDIATE")
        当前口径 = 口径.读有效(conn)
        报告 = {
            "批次编号": 批次编号,
            "入流": 0,
            "入窗": 0,
            "旁路": 0,
            "撤回": 0,
            "新关窗": 0,
            "口径": {
                "公式": 当前口径["公式"],
                "权重": 当前口径["权重"],
                "口径版本": 当前口径["口径版本"],
            },
            "明细": [],
        }
        站 = {r["键"]: r["值"] for r in conn.execute("SELECT 键, 值 FROM 站规")}
        窗长 = int(站.get("窗长秒", "60"))
        默许迟到 = int(站.get("允许迟到秒", "30"))

        for ev in 事件列表:
            房间键 = ev["房间键"]
            房 = conn.execute("SELECT * FROM 直播间 WHERE 房间键=?", (房间键,)).fetchone()
            if not 房:
                conn.execute(
                    "INSERT INTO 旁路匣(原因, 载荷, 时刻) VALUES (?,?,?)",
                    ("未知直播间", json.dumps(ev, ensure_ascii=False), 此刻()),
                )
                报告["旁路"] += 1
                报告["明细"].append({"事件编号": ev.get("事件编号"), "命运": "旁路-未知房"})
                continue

            水位 = conn.execute("SELECT * FROM 水位线 WHERE 房间键=?", (房间键,)).fetchone()
            if not 水位:
                conn.execute(
                    "INSERT INTO 水位线(房间键, 事件时水位, 允许迟到秒, 更新处理时) VALUES (?,?,?,?)",
                    (房间键, 房["开播事件时"], 默许迟到, 此刻()),
                )
                水位 = conn.execute("SELECT * FROM 水位线 WHERE 房间键=?", (房间键,)).fetchone()

            允许迟到 = int(水位["允许迟到秒"])
            事件时 = ev["事件时"]
            处理时 = ev.get("处理时") or 此刻()
            事件编号 = ev["事件编号"]
            点赞 = int(ev.get("点赞增量") or 0)
            送礼 = int(ev.get("送礼额") or 0)
            类型 = ev.get("事件类型") or "点赞"

            if conn.execute("SELECT 1 FROM 互动事件 WHERE 事件编号=?", (事件编号,)).fetchone():
                报告["明细"].append({"事件编号": 事件编号, "命运": "幂等跳过"})
                continue

            当前水位 = 水位["事件时水位"]
            if 时间.解析(事件时) > 时间.解析(当前水位):
                当前水位 = 事件时
                conn.execute(
                    "UPDATE 水位线 SET 事件时水位=?, 更新处理时=? WHERE 房间键=?",
                    (当前水位, 处理时, 房间键),
                )
            报告["新关窗"] += 热度窗.尝试关窗(
                conn, 房间键, 当前水位, 允许迟到, 窗长, 处理时, 当前口径
            )

            窗起 = 时间.对齐窗起(事件时, 窗长)
            窗止 = 时间.加秒(窗起, 窗长)
            wk = 时间.窗键(房间键, 窗起)

            
            if 热度窗.已过旁路界(当前水位, 窗止, 允许迟到):
                conn.execute(
                    """INSERT INTO 互动事件(事件编号,房间键,事件类型,事件时,处理时,观众键,点赞增量,送礼额,命运,窗键,批次编号)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        事件编号, 房间键, 类型, 事件时, 处理时,
                        ev.get("观众键") or "", 点赞, 送礼, "已旁路", "", 批次编号,
                    ),
                )
                conn.execute(
                    "INSERT INTO 旁路匣(原因, 载荷, 时刻) VALUES (?,?,?)",
                    (
                        "超允许迟到",
                        json.dumps(
                            {
                                "事件编号": 事件编号,
                                "事件时": 事件时,
                                "窗止": 窗止,
                                "旁路界": 时间.加秒(窗止, 允许迟到),
                                "水位": 当前水位,
                            },
                            ensure_ascii=False,
                        ),
                        处理时,
                    ),
                )
                报告["旁路"] += 1
                报告["明细"].append({"事件编号": 事件编号, "命运": "已旁路", "窗键本应": wk})
                continue

            窗 = conn.execute("SELECT * FROM 热度窗 WHERE 窗键=?", (wk,)).fetchone()
            if not 窗:
                conn.execute(
                    """INSERT INTO 热度窗(窗键,房间键,窗起事件时,窗止事件时,状态,点赞合计,送礼合计,事件笔数,版本)
                       VALUES (?,?,?,?, '开启', 0, 0, 0, 0)""",
                    (wk, 房间键, 窗起, 窗止),
                )
                窗 = conn.execute("SELECT * FROM 热度窗 WHERE 窗键=?", (wk,)).fetchone()
                
                if 时间.解析(当前水位) >= 时间.解析(窗止):
                    报告["新关窗"] += 热度窗.尝试关窗(
                        conn, 房间键, 当前水位, 允许迟到, 窗长, 处理时, 当前口径
                    )
                    窗 = conn.execute("SELECT * FROM 热度窗 WHERE 窗键=?", (wk,)).fetchone()

            from app.modules import 权重世代戳 as _权

            if 窗["状态"] == "已关闭":
                # 迟到写：沿用该窗冻结世代，写新戳 + 撤回单；失败整票上抛。
                结果 = _权.迟到写(
                    conn,
                    窗键=wk,
                    房间键=房间键,
                    点赞增量=点赞,
                    送礼额=送礼,
                    处理时=处理时,
                    事件编号=事件编号,
                )
                conn.execute(
                    """INSERT INTO 互动事件(事件编号,房间键,事件类型,事件时,处理时,观众键,点赞增量,送礼额,命运,窗键,批次编号,主指标权重,主指标公式版本)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        事件编号, 房间键, 类型, 事件时, 处理时,
                        ev.get("观众键") or "", 点赞, 送礼, "已入窗", wk, 批次编号,
                        int(结果["戳"]["权重值"]), 结果["戳"]["公式版本"],
                    ),
                )
                报告["入窗"] += 1
                报告["撤回"] += 1
                报告["入流"] += 1
                报告["明细"].append(
                    {
                        "事件编号": 事件编号,
                        "命运": "迟到修正撤回",
                        "窗键": wk,
                        "主指标": 结果["新主指标"],
                        "戳号": 结果["戳"]["戳号"],
                    }
                )
            else:
                # 累计写闸：窗行累计与权重世代戳同票写入，失败整票回滚。
                结果 = _权.累计写闸(
                    conn,
                    窗键=wk,
                    点赞增量=点赞,
                    送礼额=送礼,
                    公式=当前口径["公式"],
                    权重=当前口径["权重"],
                    口径版本=当前口径["口径版本"],
                    处理时=处理时,
                )
                conn.execute(
                    """INSERT INTO 互动事件(事件编号,房间键,事件类型,事件时,处理时,观众键,点赞增量,送礼额,命运,窗键,批次编号,主指标权重,主指标公式版本)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        事件编号, 房间键, 类型, 事件时, 处理时,
                        ev.get("观众键") or "", 点赞, 送礼, "已入窗", wk, 批次编号,
                        int(结果["戳"]["权重值"]), 结果["戳"]["公式版本"],
                    ),
                )
                报告["入窗"] += 1
                报告["入流"] += 1
                报告["明细"].append(
                    {
                        "事件编号": 事件编号,
                        "命运": "已入窗",
                        "窗键": wk,
                        "主指标": 结果["主指标"],
                        "戳号": 结果["戳"]["戳号"],
                    }
                )

        for 房行 in conn.execute("SELECT 房间键, 事件时水位, 允许迟到秒 FROM 水位线"):
            报告["新关窗"] += 热度窗.尝试关窗(
                conn,
                房行["房间键"],
                房行["事件时水位"],
                int(房行["允许迟到秒"]),
                窗长,
                此刻(),
                当前口径,
            )

        conn.execute(
            "INSERT INTO 装载批次(编号, 时刻, 报告) VALUES (?,?,?)",
            (批次编号, 此刻(), json.dumps(报告, ensure_ascii=False)),
        )
        conn.commit()
        return 报告
    except sqlite3.OperationalError as e:
        conn.rollback()
        raise 口径.并发冲突(f"装载遇到并发写({e})，本批已失败闭；未提交任何事件")
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

