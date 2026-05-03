# PhotoEfas - 图片隐形水印系统

基于 DCT 域的图片隐形水印系统，采用 SM2（国密）+ RSA 混合加密。只有密钥持有者可以验证水印，图片被篡改后验证自动失效。

## 功能特性

- **隐形水印** — DCT 中频系数嵌入，人眼不可察觉
- **SM2 + RSA 混合加密** — SM2 数字签名保证完整性 + RSA-OAEP 保证机密性
- **抗压缩** — 重复编码 + 多数投票纠错，可抵抗 JPEG Q=50-70 压缩（微信传图）
- **邀请码注册** — 管理员生成邀请码，用户凭码注册
- **角色权限** — 管理员管理密钥、嵌入水印；用户使用私钥验证
- **格式保持** — PNG 输入输出 PNG，JPG 输入输出 JPG，不破坏水印
- **自动清理** — 启动时清理过期文件，后台定时清理（每6小时）
- **安全防护** — 文件内容验证(Magic Bytes)、XSS 防护、开放重定向防护、路径遍历防护
- **跨平台** — Windows / Linux / macOS

## 快速启动

### Windows

双击 `start.bat`，自动创建虚拟环境、安装依赖、启动服务。

### Linux / macOS

```bash
chmod +x start.sh
./start.sh
```

### 手动启动

```bash
python -m venv venv

# Windows
venv\Scripts\pip install -r requirements.txt
venv\Scripts\python init_db.py
venv\Scripts\python run.py

# Linux / macOS
venv/bin/pip install -r requirements.txt
venv/bin/python init_db.py
venv/bin/python run.py
```

浏览器访问 http://localhost:5000

**默认管理员：** `admin` / `admin123`

> 首次启动后请立即修改管理员密码。SECRET_KEY 自动生成并持久化到 `instance/.secret_key`。

## 使用流程

### 管理员操作

1. 登录管理后台
2. 生成 SM2 + RSA 密钥对
3. 生成邀请码并分发给用户
4. 上传图片，输入水印文本，选择嵌入强度(Alpha)，嵌入水印
5. 下载水印图片，将 **RSA 私钥**和 **SM2 公钥**提供给用户

### 用户操作

1. 使用邀请码注册账户
2. 登录后在"我的密钥"页面上传管理员提供的 RSA 私钥和 SM2 公钥
3. 上传待验证图片（注意 Alpha 值需与嵌入时一致）
4. 系统自动提取水印并验证签名

## 技术原理

### 嵌入流程

```
原图 → SHA256哈希 → SM2签名 → 构建Payload → RSA加密 → 重复编码 → DCT嵌入 → 水印图
```

### 验证流程

```
水印图 → DCT提取 → 重复解码 → RSA解密 → 解析Payload → SM2验签 → 结果
```

### 加密方案

| 组件   | 算法                   | 用途                |
| ------ | ---------------------- | ------------------- |
| 哈希   | SM3                    | 图片内容256位哈希   |
| 签名   | SM2 (GM/T 0003)        | 完整性 + 不可否认性 |
| 加密   | RSA-2048 OAEP          | Payload 机密性      |
| 纠错   | 3x 重复编码 + 多数投票 | 抵抗 JPEG 压缩      |
| 水印域 | DCT 8x8 块             | 抗图像处理          |

### 水印容量

| 图片尺寸  | 可用块数 | 比特数 (4位/块) | 最大 Payload |
| --------- | -------- | --------------- | ------------ |
| 512×512   | 4,096    | 16,384          | ~500 字节    |
| 1024×768  | 12,288   | 49,152          | ~1.5 KB      |
| 1920×1080 | 32,400   | 129,600         | ~4 KB        |

## 微信传图抗性

微信会将图片压缩为 JPEG Q=50-70 并可能缩放尺寸。本系统采用多层保护：

1. **DCT 中频系数** — 选择抗 JPEG 量化的位置嵌入
2. **JPEG 量化表缩放** — 嵌入步长参照标准量化表
3. **动态冗余** — 根据图片大小自动调整 1-4 倍冗余
4. **重复编码** — 3 倍重复 + 多数投票进行比特级纠错

使用建议：

- 图片尺寸建议 **大于 1024×768**
- 微信发送时选择**原图**发送
- PNG 格式比 JPEG 更鲁棒

## 安全措施

| 攻击类型          | 防护措施                                          |
| ----------------- | ------------------------------------------------- |
| 恶意文件上传      | Magic Bytes 内容验证 + 扩展名白名单 + UUID 文件名 |
| 双写绕过          | 文件名完全随机化，不使用原始文件名                |
| PHP/JSP/ASPX 解析 | 仅允许图片格式（PNG/JPG/BMP），非图片文件直接拒绝 |
| 路径遍历          | UUID 文件名 + 下载路径验证                        |
| XSS               | Jinja2 自动转义 + data 属性替代 JS 拼接           |
| 开放重定向        | next 参数仅允许站内相对路径                       |
| SQL 注入          | 全量使用 SQLAlchemy ORM，无原始 SQL               |
| 硬编码密钥        | 自动生成随机 SECRET_KEY 并持久化                  |

## 项目结构

```
photoefas/
├── app.py                  # 入口
├── run.py                  # 开发服务器
├── config.py               # 配置（自动生成 SECRET_KEY）
├── init_db.py              # 初始化数据库
├── requirements.txt        # 依赖
├── .gitignore              # Git 忽略规则
├── start.bat               # Windows 一键启动
├── start.sh                # Linux/macOS 一键启动
├── _server.bat             # Windows 服务窗口
├── app/
│   ├── __init__.py         # Flask 工厂 + 启动清理 + 定时清理
│   ├── models.py           # 数据模型 (User, KeyPair, WatermarkRecord, InviteCode)
│   ├── extensions.py       # Flask 扩展
│   ├── core/
│   │   ├── crypto.py       # SM2 签名/验签 + RSA 加解密
│   │   ├── dct_watermark.py # DCT 域水印嵌入/提取
│   │   ├── bch_codec.py    # 重复纠错编码
│   │   └── watermark_engine.py # 水印编排器
│   ├── auth/               # 登录 / 注册 / 登出
│   ├── admin/              # 管理后台：密钥管理、嵌入水印、验证、邀请码、清理
│   ├── user/               # 用户面板：上传密钥、验证图片
│   ├── api/                # REST API
│   ├── templates/          # Jinja2 模板
│   ├── static/             # CSS / JS
│   └── utils/
│       ├── helpers.py      # 文件上传验证 + Magic Bytes
│       └── cleanup.py      # 文件清理工具
├── uploads/                # 上传的原始图片（自动清理）
├── outputs/                # 嵌入水印后的图片（自动清理）
└── instance/               # SQLite 数据库 + SECRET_KEY
```

## API 接口

| 方法 | 路径           | 说明                                                         |
| ---- | -------------- | ------------------------------------------------------------ |
| POST | `/api/embed`   | 嵌入水印 (multipart: image, watermark_text, alpha)           |
| POST | `/api/verify`  | 验证水印 (multipart: image, rsa_private_key, sm2_public_key) |
| GET  | `/api/keys`    | 获取公钥列表                                                 |
| GET  | `/api/records` | 获取水印记录                                                 |

## 依赖

```
flask
flask-sqlalchemy
flask-login
opencv-python-headless
numpy
gmssl
pycryptodome
Pillow
scipy
```

## 技术栈

- **后端：** Flask, SQLAlchemy, Flask-Login
- **加密：** gmssl (SM2/SM3), pycryptodome (RSA)
- **图像处理：** OpenCV, NumPy, SciPy
- **数据库：** SQLite
- **前端：** 原生 HTML / CSS / JS

