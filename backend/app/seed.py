from datetime import datetime, timezone

from app.db import 连接

建表 = """
CREATE TABLE IF NOT EXISTS 权重世代戳 (
  编号 INTEGER PRIMARY KEY AUTOINCREMENT,
  窗键 TEXT NOT NULL,
  权重值 TEXT NOT NULL DEFAULT '',
  公式版本 TEXT NOT NULL DEFAULT '',
  累计主指标 INTEGER NOT NULL DEFAULT 0,
  戳号 TEXT NOT NULL DEFAULT '',
  时刻 TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS 站规 (
  键 TEXT PRIMARY KEY,
  值 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS 直播间 (
  房间键 TEXT PRIMARY KEY,
  标题 TEXT NOT NULL,
  主播 TEXT NOT NULL,
  开播事件时 TEXT NOT NULL,
  状态 TEXT NOT NULL DEFAULT '直播中'
);
CREATE TABLE IF NOT EXISTS 互动事件 (
  事件编号 TEXT PRIMARY KEY,
  房间键 TEXT NOT NULL REFERENCES 直播间(房间键),
  事件类型 TEXT NOT NULL,
  事件时 TEXT NOT NULL,
  处理时 TEXT NOT NULL,
  观众键 TEXT NOT NULL DEFAULT '',
  点赞增量 INTEGER NOT NULL DEFAULT 0,
  送礼额 INTEGER NOT NULL DEFAULT 0,
  命运 TEXT NOT NULL DEFAULT '已入流',
  窗键 TEXT NOT NULL DEFAULT '',
  批次编号 TEXT NOT NULL DEFAULT '',
  主指标权重 INTEGER NOT NULL DEFAULT 0,
  主指标公式版本 TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS 装载批次 (
  编号 TEXT PRIMARY KEY,
  时刻 TEXT NOT NULL,
  报告 TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS 水位线 (
  房间键 TEXT PRIMARY KEY REFERENCES 直播间(房间键),
  事件时水位 TEXT NOT NULL,
  允许迟到秒 INTEGER NOT NULL DEFAULT 30,
  更新处理时 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS 热度窗 (
  窗键 TEXT PRIMARY KEY,
  房间键 TEXT NOT NULL REFERENCES 直播间(房间键),
  窗起事件时 TEXT NOT NULL,
  窗止事件时 TEXT NOT NULL,
  状态 TEXT NOT NULL DEFAULT '开启',
  点赞合计 INTEGER NOT NULL DEFAULT 0,
  送礼合计 INTEGER NOT NULL DEFAULT 0,
  事件笔数 INTEGER NOT NULL DEFAULT 0,
  关闭处理时 TEXT NOT NULL DEFAULT '',
  版本 INTEGER NOT NULL DEFAULT 0,
  主指标 INTEGER NOT NULL DEFAULT 0,
  主指标公式 TEXT NOT NULL DEFAULT '',
  主指标权重 INTEGER NOT NULL DEFAULT 0,
  口径版本 INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS 撤回单 (
  编号 INTEGER PRIMARY KEY AUTOINCREMENT,
  窗键 TEXT NOT NULL,
  房间键 TEXT NOT NULL,
  原因 TEXT NOT NULL,
  旧点赞 INTEGER NOT NULL,
  新点赞 INTEGER NOT NULL,
  旧送礼 INTEGER NOT NULL,
  新送礼 INTEGER NOT NULL,
  处理时 TEXT NOT NULL,
  事件编号 TEXT NOT NULL DEFAULT '',
  旧主指标 INTEGER NOT NULL DEFAULT 0,
  新主指标 INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS 旁路匣 (
  编号 INTEGER PRIMARY KEY AUTOINCREMENT,
  原因 TEXT NOT NULL,
  载荷 TEXT NOT NULL,
  时刻 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS 窗贯验 (
  编号 INTEGER PRIMARY KEY AUTOINCREMENT,
  时刻 TEXT NOT NULL,
  事件数 INTEGER NOT NULL,
  已关闭窗数 INTEGER NOT NULL,
  撤回数 INTEGER NOT NULL,
  旁路数 INTEGER NOT NULL,
  是否通过 INTEGER NOT NULL,
  说明 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS 热度口径变更 (
  编号 INTEGER PRIMARY KEY AUTOINCREMENT,
  时刻 TEXT NOT NULL,
  旧公式 TEXT NOT NULL,
  新公式 TEXT NOT NULL,
  旧权重 INTEGER NOT NULL,
  新权重 INTEGER NOT NULL,
  旧版本 INTEGER NOT NULL,
  新版本 INTEGER NOT NULL,
  说明 TEXT NOT NULL
);
"""


热度窗补列 = {
    "主指标": "INTEGER NOT NULL DEFAULT 0",
    "主指标公式": "TEXT NOT NULL DEFAULT ''",
    "主指标权重": "INTEGER NOT NULL DEFAULT 0",
    "口径版本": "INTEGER NOT NULL DEFAULT 0",
}
撤回单补列 = {
    "旧主指标": "INTEGER NOT NULL DEFAULT 0",
    "新主指标": "INTEGER NOT NULL DEFAULT 0",
}
互动事件补列 = {
    "主指标权重": "INTEGER NOT NULL DEFAULT 0",
    "主指标公式版本": "TEXT NOT NULL DEFAULT ''",
}


def 此刻() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def 初始化库() -> None:
    conn = 连接()
    try:
        
        conn.executescript(建表)
        conn.execute("BEGIN IMMEDIATE")
        if conn.execute("SELECT COUNT(*) AS c FROM 站规").fetchone()["c"] == 0:
            for k, v in {
                "站名": "播浪",
                "窗长秒": "60",
                "允许迟到秒": "30",
                "水位推进策略": "事件时最大值",
                "关窗条件": "水位>=窗止即关闭发射",
                "旁路条件": "水位>=窗止+允许迟到",
                "骨架": "互动事件入流→事件时间水位线推进→热度窗关闭发射→迟到修正撤回→窗输出与撤回互证",
                "热度公式": "金额加权",
                "送礼权重": "2",
                "口径版本": "0",
            }.items():
                conn.execute("INSERT INTO 站规(键, 值) VALUES (?, ?)", (k, v))
        
        已有 = {r["键"] for r in conn.execute("SELECT 键 FROM 站规")}
        for k, v in {"热度公式": "金额加权", "送礼权重": "2", "口径版本": "0"}.items():
            if k not in 已有:
                conn.execute("INSERT INTO 站规(键, 值) VALUES (?, ?)", (k, v))
        迁移热度窗(conn)
        迁移权重戳(conn)
        if conn.execute("SELECT COUNT(*) AS c FROM 直播间").fetchone()["c"] == 0:
            conn.execute(
                "INSERT INTO 直播间(房间键, 标题, 主播, 开播事件时, 状态) VALUES (?,?,?,?,?)",
                ("房A", "晚间热聊", "主播小浪", "2026-11-22T12:00:00Z", "直播中"),
            )
            conn.execute(
                "INSERT INTO 水位线(房间键, 事件时水位, 允许迟到秒, 更新处理时) VALUES (?,?,?,?)",
                ("房A", "2026-11-22T12:00:00Z", 30, 此刻()),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def 迁移权重戳(conn) -> None:
    """为历史已累计但缺戳的窗补写一枚权重世代戳（取窗行冻结世代）。

    口径：入窗戳冻结发射。老库里的窗行已有冻结公式/权重/主指标，
    补戳只是把同世代钉死，不改任何累计值；戳内主指标 = 窗行主指标。
    """
    from app.modules import 权重世代戳 as 权

    for 窗 in conn.execute(
        "SELECT * FROM 热度窗 WHERE 事件笔数>0"
    ).fetchall():
        if conn.execute(
            "SELECT 1 FROM 权重世代戳 WHERE 窗键=? LIMIT 1", (窗["窗键"],)
        ).fetchone():
            continue
        公式 = (窗["主指标公式"] or "").strip()
        if not 公式:
            # 无冻结公式的旧窗无法安全补戳；保持无戳，发射/修正会失败闭。
            continue
        try:
            权.打戳(
                conn,
                窗键=窗["窗键"],
                公式=公式,
                权重=int(窗["主指标权重"]),
                口径版本=int(窗["口径版本"] or 0),
                累计主指标=int(窗["主指标"] or 0),
                时刻=窗["关闭处理时"] or 此刻(),
            )
        except 权.戳异常:
            # 补戳失败不阻塞启动；该窗后续发射/修正将失败闭，绝不按现行权重回溯。
            continue


def 迁移热度窗(conn) -> None:
    """补主指标列；对早已关闭但未冻结口径的窗，按当时站规补冻结值。"""
    from app.services import 口径

    列 = {r["name"] for r in conn.execute("PRAGMA table_info(撤回单)")}
    for 名, 定义 in 撤回单补列.items():
        if 名 not in 列:
            conn.execute(f"ALTER TABLE 撤回单 ADD COLUMN {名} {定义}")

    列 = {r["name"] for r in conn.execute("PRAGMA table_info(互动事件)")}
    for 名, 定义 in 互动事件补列.items():
        if 名 not in 列:
            conn.execute(f"ALTER TABLE 互动事件 ADD COLUMN {名} {定义}")

    列 = {r["name"] for r in conn.execute("PRAGMA table_info(热度窗)")}
    新加 = [名 for 名 in 热度窗补列 if 名 not in 列]
    for 名 in 新加:
        conn.execute(f"ALTER TABLE 热度窗 ADD COLUMN {名} {热度窗补列[名]}")
    if not 新加:
        return

    当前 = 口径.读当前(conn)
    公式 = 当前["公式"] if 当前["valid"] else ""
    权重 = int(当前["权重"])
    if 公式:
        for 窗 in conn.execute(
            "SELECT * FROM 热度窗 WHERE 状态='已关闭' AND 主指标公式=''"
        ).fetchall():
            主 = 口径.计算(公式, 窗["点赞合计"], 窗["送礼合计"], 权重)
            conn.execute(
                "UPDATE 热度窗 SET 主指标=?, 主指标公式=?, 主指标权重=?, 口径版本=? WHERE 窗键=?",
                (主, 公式, 权重, int(当前["口径版本"]), 窗["窗键"]),
            )

