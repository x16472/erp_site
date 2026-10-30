"""銀盾共同體系統的權威時間服務。

所有會顯示或寫入出勤時間的流程，都由 SQL Server 取得同一次時間快照；
瀏覽器再以 API 往返時間校正本機時鐘，避免各頁各自相信裝置時間。
"""

from __future__ import annotations

from typing import Any


def now(cursor: Any) -> dict[str, Any]:
    """透過既有資料庫游標取得帶時區的現在時間與當地工作日。"""
    row = cursor.execute('time_sync.now.1').fetchone()
    return {
        "offset_time": row[0],
        "local_time": row[1],
        "work_date": row[2],
        "iso_time": row[3],
        "unix_ms": int(row[4]),
        "utc_time": row[5],
    }
