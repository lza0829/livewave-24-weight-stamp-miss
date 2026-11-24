"""热度口径：全局单选的公式、权重与「已关窗冻结」规则。

口径在全站任一时刻只有一种：

- 金额加权：主指标 = 点赞增量 + 送礼额 × 权重；送礼额进入发射与互证。
- 等权计数：主指标 = 点赞增量；送礼额只旁路展示，绝不进入主指标。

硬约束：

- 加权入窗成功即写权重世代戳；关窗事务内窗行主指标/公式/权重/口径版本取自
  同一枚最新戳（入窗戳冻结发射），改口径不得回写已累计。
- 关窗后仍在允许迟到内的修正，沿用该窗冻结世代；互证也按逐笔世代累进重算。
- 装载（含关窗、迟到修正）与改口径共用一把锁；改口径拿不到锁即失败闭，
  不排队、不半截提交，避免「发射按旧公式、互证按新公式」。
"""
import sqlite3
import threading
from datetime import datetime, timezone

from app.db import 连接

公式表 = {
    "金额加权": {
        "主指标": "点赞增量 + 送礼额 × 权重",
        "送礼进主指标": True,
        "说明": "点赞按 1 计，送礼额按站规权重折算后进入主指标。",
    },
    "等权计数": {
        "主指标": "点赞增量",
        "送礼进主指标": False,
        "说明": "只以点赞增量计数；送礼额仅在窗明细旁路展示，不进主指标。",
    },
}
可选公式 = list(公式表)


锁 = threading.RLock()


class 口径无效(Exception):
    """站规中的公式或权重不可用。装载与关窗遇到时整体回滚。"""


class 并发冲突(Exception):
    """改口径与装载 / 关窗并发交错，本次变更未提交。"""


class 版本冲突(并发冲突):
    """调用方持有的口径版本已过期，本次变更未提交。"""


def 此刻() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def 计算(公式: str, 点赞: int, 送礼: int, 权重: int) -> int:
    """按公式计算主指标。等权口径下送礼额无条件为 0 权重。"""
    if 公式 == "金额加权":
        return int(点赞) + int(送礼) * int(权重)
    if 公式 == "等权计数":
        return int(点赞)
    raise 口径无效(f"未知热度公式:{公式}")


def 表达式(公式: str) -> str:
    return 公式表.get(公式, {}).get("主指标", "")


def 主指标零因(
    公式: str, 权重: int, 点赞: int, 送礼: int, 笔数: int, 主指标: int
) -> str:
    """主指标为 0 时给出可区分的原因；非 0 返回空串。

    纯送礼窗在等权口径下主指标为 0，与「空窗 / 真的没有热度」必须可区分；
    金额加权口径下同一窗主指标为 送礼×权重（权重为 0 时另行说明）。
    """
    if 主指标 != 0:
        return ""
    if 公式 not in 公式表:
        return f"口径不可用（{公式}）"
    if 笔数 == 0:
        return "空窗"
    if 点赞 == 0 and 送礼 > 0:
        if 公式 == "等权计数":
            return "等权口径不计送礼（纯送礼窗）"
        if 公式 == "金额加权" and int(权重) == 0:
            return "权重为零，不计送礼（纯送礼窗）"
    return "合计为零"


def _解析权重(raw) -> int | None:
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return None
    if n < 0 or n > 100000:
        return None
    return n


def 读当前(conn) -> dict:
    """只读：返回全局选定公式、权重、主指标表达式与 valid。

    valid=False 表示站规被写坏；此时装载 / 关窗会失败闭，不会半截发射。
    """
    规 = {r["键"]: r["值"] for r in conn.execute("SELECT 键, 值 FROM 站规")}
    公式 = (规.get("热度公式") or "").strip()
    权重 = _解析权重(规.get("送礼权重"))
    try:
        版本 = int(规.get("口径版本") or 0)
    except (TypeError, ValueError):
        版本 = 0
    valid = 公式 in 公式表 and 权重 is not None
    表 = 公式表.get(公式, {})
    return {
        "公式": 公式,
        "权重": 权重 if 权重 is not None else 0,
        "主指标": 表达式(公式) if 公式 in 公式表 else "",
        "主指标表达式": 表达式(公式) if 公式 in 公式表 else "",
        "送礼进主指标": bool(表.get("送礼进主指标", False)),
        "valid": valid,
        "口径版本": 版本,
        "可选公式": 可选公式,
        "已关窗冻结": True,
        "说明": 表.get("说明", "公式或权重无效，装载/关窗将失败闭。"),
    }


def 读有效(conn) -> dict:
    d = 读当前(conn)
    if not d["valid"]:
        raise 口径无效(
            f"热度口径无效(公式={d['公式']!r}, 权重={d['权重']!r})，本次操作已失败闭"
        )
    return d


def 装饰窗(窗, 当前: dict) -> dict:
    """给窗补上主指标视图：已关窗用冻结口径，开启窗按当前口径预演。

    开启窗若已累计（窗行冻结世代非空），主指标取累计值与其钉死世代，
    不再按当前口径重算——入窗戳冻结发射，改权重不得回溯已累计。
    """
    d = dict(窗)
    已关 = d.get("状态") == "已关闭"
    冻结公式 = (d.get("主指标公式") or "").strip()
    if 已关:
        公式 = 冻结公式
        权重 = _解析权重(d.get("主指标权重"))
        冻结 = bool(公式)
        if not 冻结:
            公式 = "未冻结"
            权重 = 0
            主指标 = int(d.get("主指标") or 0)
            版本 = int(d.get("口径版本") or 0)
        else:
            主指标 = int(d.get("主指标") or 0)
            版本 = int(d.get("口径版本") or 0)
    elif 冻结公式:
        公式 = 冻结公式
        权重 = _解析权重(d.get("主指标权重"))
        冻结 = True
        主指标 = int(d.get("主指标") or 0)
        版本 = int(d.get("口径版本") or 0)
    else:
        公式 = 当前["公式"] if 当前["valid"] else "无效"
        权重 = int(当前["权重"])
        冻结 = False
        版本 = int(当前["口径版本"])
        if 当前["valid"]:
            主指标 = 计算(公式, int(d.get("点赞合计") or 0), int(d.get("送礼合计") or 0), 权重)
        else:
            主指标 = 0

    d["公式"] = 公式
    d["权重"] = int(权重 or 0)
    d["主指标"] = 主指标
    d["冻结"] = 冻结
    d["口径版本"] = 版本
    d["主指标零因"] = 主指标零因(
        公式,
        int(权重 or 0),
        int(d.get("点赞合计") or 0),
        int(d.get("送礼合计") or 0),
        int(d.get("事件笔数") or 0),
        主指标,
    )
    return d


def 读变更(conn, 限: int = 50) -> list:
    return [
        dict(r)
        for r in conn.execute(
            "SELECT * FROM 热度口径变更 ORDER BY 编号 DESC LIMIT ?", (int(限),)
        )
    ]


def 改口径(体: dict) -> dict:
    """改全局口径。与装载/关窗并发时失败闭（409），绝不部分提交。"""
    目标公式 = 体.get("公式")
    目标权重 = 体.get("权重")
    期望版本 = 体.get("期望版本")

    if 目标公式 is not None and 目标公式 not in 公式表:
        raise 口径无效(f"未知热度公式:{目标公式}")
    if 目标权重 is not None:
        解析后 = _解析权重(目标权重)
        if 解析后 is None:
            raise 口径无效("送礼权重须为 0..100000 的整数")
        目标权重 = 解析后
    if 期望版本 is not None:
        try:
            期望版本 = int(期望版本)
        except (TypeError, ValueError):
            raise 口径无效("期望版本须为整数")

    if not 锁.acquire(blocking=False):
        raise 并发冲突("口径变更与装载/关窗并发交错，已失败闭；本次未提交")

    
    conn = 连接(忙等毫秒=0)
    try:
        conn.execute("BEGIN IMMEDIATE")
        旧 = 读有效(conn)
        if 期望版本 is not None and int(旧["口径版本"]) != 期望版本:
            raise 版本冲突(
                f"口径版本已变化(期望 {期望版本}，当前 {旧['口径版本']})，本次未提交"
            )

        新公式 = 旧["公式"] if 目标公式 is None else 目标公式
        新权重 = int(旧["权重"]) if 目标权重 is None else int(目标权重)
        新版本 = int(旧["口径版本"]) + 1
        变更 = 新公式 != 旧["公式"] or 新权重 != int(旧["权重"])

        if 变更:
            conn.execute(
                "UPDATE 站规 SET 值=? WHERE 键='热度公式'", (新公式,)
            )
            conn.execute(
                "UPDATE 站规 SET 值=? WHERE 键='送礼权重'", (str(新权重),)
            )
            conn.execute(
                "UPDATE 站规 SET 值=? WHERE 键='口径版本'", (str(新版本),)
            )
            说明 = (
                f"{旧['公式']}(权重{旧['权重']}) → {新公式}(权重{新权重})；"
                "已关窗发射结果不变，后续关窗按新口径冻结"
            )
            conn.execute(
                """INSERT INTO 热度口径变更(时刻,旧公式,新公式,旧权重,新权重,旧版本,新版本,说明)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (
                    此刻(),
                    旧["公式"],
                    新公式,
                    int(旧["权重"]),
                    新权重,
                    int(旧["口径版本"]),
                    新版本,
                    说明,
                ),
            )
        conn.commit()
        当前 = 读当前(conn)
        当前["变更"] = 变更
        当前["变更说明"] = (
            f"{旧['公式']}(权重{旧['权重']}) → {新公式}(权重{新权重})"
            if 变更
            else "口径未变化"
        )
        return 当前
    except sqlite3.OperationalError as e:
        conn.rollback()
        raise 并发冲突(f"口径变更遇到并发写({e})，已失败闭；本次未提交")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
        锁.release()
