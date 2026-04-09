"""
麻雀AIサーバー起動スクリプト
Usage: python run.py
"""
import sys
import os

# Windows cp932 エンコード問題を回避
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import uvicorn

if __name__ == "__main__":
    print("=" * 50)
    print("  Mahjong AI Server")
    print("  http://127.0.0.1:8080")
    print("=" * 50)
    uvicorn.run(
        "server.app:app",
        host="127.0.0.1",
        port=8080,
        reload=True,
        log_level="info",
    )
