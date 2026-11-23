
"""热度口径自检：不依赖 pytest，用临时库跑三组必验夹具。

    python3 scripts/口径校验.py

1. 同一纯送礼窗：等权口径主指标为 0（并给出零因），金额加权口径为 送礼×权重。
2. 改权重不回写已关窗；之后关闭的窗按新权重冻结。
3. 改公式与关窗（装载持锁）并发：改口径失败闭，站规与已关窗都不半截。
"""
import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

根 = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(根 / "backend"))
夹具 = 根 / "fixtures"

失败 = []


def 断言(条件, 说明):
    print(("  ok  " if 条件 else "  FAIL") + "  " + 说明)
    if not 条件:
        失败.append(说明)


def 新环境(公式="金额加权", 权重=2):
    """独立临时库 + 重新导入 app 模块（db.py 在 import 时读取数据目录）。"""
    目录 = tempfile.mkdtemp(prefix="播浪-口径-")
    os.environ["数据目录"] = 目录
    os.environ["夹具目录"] = str(夹具)
    for 名 in list(sys.modules):
        if 名 == "app" or 名.startswith("app."):
            del sys.modules[名]
    from app import seed
    from app.db import 连接
    from app.services import 口径, 装载, 贯验

    seed.初始化库()
    if 公式 != "金额加权" or 权重 != 2:
        口径.改口径({"公式": 公式, "权重": 权重})
    return {"口径": 口径, "装载": 装载, "贯验": 贯验, "连接": 连接}


def 装(M, 名):
    return M["装载"].装一批(json.loads((夹具 / f"{名}.json").read_text(encoding="utf-8")))


def 窗(M):
    c = M["连接"]()
    try:
        return {
            r["窗键"]: dict(r)
            for r in c.execute("SELECT * FROM 热度窗 ORDER BY 窗起事件时")
        }
    finally:
        c.close()


def 只送礼窗键(M):
    c = M["连接"]()
    try:
        r = c.execute(
            "SELECT 窗键 FROM 热度窗 WHERE 点赞合计=0 AND 送礼合计>0 ORDER BY 窗起事件时 LIMIT 1"
        ).fetchone()
        return r["窗键"] if r else None
    finally:
        c.close()


print("== 1. 同窗一笔纯送礼：甲 0，乙 加权值 ==")
甲 = 新环境("等权计数", 2)
装(甲, "纯送礼样例")
w甲 = 窗(甲)[只送礼窗键(甲)]
断言(w甲["主指标"] == 0 and w甲["主指标公式"] == "等权计数", "等权口径主指标=0")
断言(
    甲["口径"].装饰窗(甲["连接"]().execute(
        "SELECT * FROM 热度窗 WHERE 窗键=?", (w甲["窗键"],)
    ).fetchone(), 甲["口径"].读当前(甲["连接"]()))["主指标零因"]
    == "等权口径不计送礼（纯送礼窗）",
    "等权口径 0 值有零因，可与空窗区分",
)
乙 = 新环境("金额加权", 2)
装(乙, "纯送礼样例")
w乙 = 窗(乙)[只送礼窗键(乙)]
断言(w乙["主指标"] == w乙["送礼合计"] * 2, f"金额加权主指标={w乙['送礼合计']}×2={w乙['主指标']}")

print("== 2. 改权重不撬已关窗 ==")
M = 新环境("金额加权", 2)
装(M, "纯送礼样例")
前 = 窗(M)[只送礼窗键(M)]
M["口径"].改口径({"权重": 5})
后 = 窗(M)[只送礼窗键(M)]
断言(前["主指标"] == 后["主指标"] and 后["主指标权重"] == 2, "改权重 2→5 后已关窗主指标与冻结权重不变")
断言(M["贯验"].跑贯验()["是否通过"], "互证按冻结口径通过")

print("== 3. 改公式与关窗并发：失败闭 ==")
M = 新环境("金额加权", 2)
装(M, "纯送礼样例")
前版本 = M["口径"].读当前(M["连接"]())["口径版本"]
前窗 = 窗(M)
结果 = {}


def 改():
    time.sleep(0.05)
    try:
        结果["r"] = M["口径"].改口径({"公式": "等权计数", "权重": 2})
    except M["口径"].并发冲突 as e:
        结果["e"] = str(e)


M["口径"].锁.acquire()  
t = threading.Thread(target=改)
t.start()
time.sleep(0.3)
M["口径"].锁.release()
t.join()
断言("e" in 结果 and "r" not in 结果, f"并发改口径被拒: {结果.get('e')}")
当前 = M["口径"].读当前(M["连接"]())
断言(当前["公式"] == "金额加权" and 当前["口径版本"] == 前版本, "站规未被半截改写")
断言(窗(M) == 前窗, "已关窗发射结果未变")
断言(not M["口径"].读变更(M["连接"]()), "失败变更未留记录")

print()
if 失败:
    print(f"失败 {len(失败)} 项")
    sys.exit(1)
print("全部通过")
