import os
import sqlite3
from pathlib import Path

数据目录 = Path(os.environ.get("数据目录", Path(__file__).resolve().parent.parent / "data"))
夹具目录 = Path(os.environ.get("夹具目录", Path(__file__).resolve().parent.parent.parent / "fixtures"))
库路径 = 数据目录 / "播浪.db"


def 连接(忙等毫秒: int = 5000) -> sqlite3.Connection:
    """打开连接。

    isolation_level=None：显式 BEGIN IMMEDIATE 控制事务边界，装载/关窗/改口径都整笔提交，
    不会因 Python 隐式事务产生半截。
    busy_timeout 决定写锁竞争时等待多久；改口径传 0 以便并发时立刻失败闭。
    """
    数据目录.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(库路径, timeout=max(忙等毫秒, 0) / 1000, isolation_level=None)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    c.execute(f"PRAGMA busy_timeout = {int(忙等毫秒)}")
    return c
