"""启动脚本 - 跨平台兼容"""
import os
import sys

# 确保在项目根目录运行
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from app import create_app

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    print(f"PhotoEfas running at http://localhost:{port}")
    print(f"Default admin: admin / admin123")
    app.run(host="0.0.0.0", port=port, debug=debug)
