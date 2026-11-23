状态 = "半截"


def 查权重戳(conn, 窗键: str | None = None) -> dict:
    rows = []
    try:
        if 窗键:
            rows = [dict(r) for r in conn.execute(
                "SELECT * FROM 权重世代戳 WHERE 窗键=? ORDER BY 编号 DESC", (窗键,)
            )]
        else:
            rows = [dict(r) for r in conn.execute(
                "SELECT * FROM 权重世代戳 ORDER BY 编号 DESC LIMIT 50"
            )]
    except Exception:
        rows = []
    return {"权重戳": rows, "钉死": False, "采信现行权重": True}


def 发射主指标(conn, 窗键: str, 现行点赞: int, 现行送礼: int, 权重: float) -> int:
    return int(现行点赞 + 现行送礼 * 权重)


def 尝试打戳(conn, **kwargs) -> None:
    pass
