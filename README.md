# AI 火灾检测与监控系统

基于 `FastAPI + Vue 3 + Qwen-VL + MySQL` 的火灾识别与监控记录系统，包含：
- 手动上传图片识别
- 脚本自动上传识别（文件夹监听）
- 数据监控记录（增删改查、排序）
- 识别后自动生成监控记录

## 1. 项目结构

```text
fire_detection/
|-- backend/                      # FastAPI 后端
|   |-- app_factory.py            # 应用工厂、生命周期、静态资源挂载
|   |-- config.py                 # 环境变量配置
|   |-- database.py               # SQLAlchemy 异步数据库连接
|   |-- main.py                   # FastAPI 入口
|   |-- routers/
|   |   |-- detect.py             # 火灾检测接口 + WebSocket
|   |   `-- data_monitor.py       # 数据监控记录 CRUD + 排序
|   |-- services/
|   |   |-- qwen_client.py        # Qwen 接口调用
|   |   |-- monitor_records.py    # 监控记录与图片存储服务
|   |   `-- script_uploader.py    # 自动上传脚本进程管理
|   |-- models/                   # ORM 与 Pydantic 模型
|   |-- scripts/rebuild_monitor_records.py
|   |-- detected_frames/          # 自动上传监听目录（脚本输入）
|   |-- data_image/               # 监控记录图片目录（数据库记录引用）
|   `-- requirements.txt
|-- frontend/                     # Vue 3 + Vite 前端
|   |-- src/
|   |   |-- App.vue               # 页面主逻辑
|   |   |-- components/           # 页面拆分组件
|   |   |-- services/fireApi.js   # 前端 API 封装
|   |   |-- composables/useScriptSocket.js
|   |   |-- utils/format.js
|   |   `-- config/api.js
|   `-- package.json
`-- python/                       # 本地自动上传与 YOLO 脚本
    |-- main.py                   # 监听目录并自动上传图片到后端
    |-- upload_image.py           # 单张/批量上传工具
    `-- yolo.py                   # YOLO 检测并落图到 detected_frames
```

## 2. 核心流程

### 2.1 手动检测流程
1. 前端上传图片到 `POST /api/manual/detect-fire`
2. 后端调用 Qwen 识别火灾
3. 后端自动创建一条监控记录（含图片落盘到 `backend/data_image`）
4. 返回识别结果与 `monitor_record`

### 2.2 自动检测流程（脚本上传）
1. `python/main.py` 监听 `backend/detected_frames`
2. 有新图时调用 `POST /api/script/detect-fire`
3. 后端识别并自动入库监控记录
4. 后端通过 WebSocket `/ws/script/latest-upload-image` 推送最新图像与结果给前端

### 2.3 数据监控
- 列表查询：`GET /api/data-monitor/records`
- 支持排序参数：
  - `sort_by`: `id | status | remark | created_at | updated_at | time`
  - `sort_order`: `asc | desc`
- 支持新增 / 编辑 / 删除记录

## 3. 环境要求

- Python `3.10+`（建议）
- Node.js `18+`
- MySQL `8+`（或兼容版本）

## 4. 后端启动

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

创建环境变量文件：

```powershell
copy .env.example .env
```

`.env` 关键配置：

```env
QWEN_API_KEY=
QWEN_MODEL=qwen-vl-plus
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

MYSQL_URL=
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=
MYSQL_DATABASE=fire_detection
MYSQL_CHARSET=utf8mb4

SCRIPT_UPLOADER_ENABLED=true
SCRIPT_UPLOADER_WATCH_DIR=detected_frames
DATA_IMAGE_DIR=data_image
SCRIPT_UPLOADER_ENDPOINT=http://127.0.0.1:8000/api/script/detect-fire
```

启动服务：

```powershell
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

后端默认地址：`http://127.0.0.1:8000`

## 5. 前端启动

```powershell
cd frontend
npm install
copy .env.example .env
npm run dev
```

默认前端地址：`http://127.0.0.1:5173`

## 6. Python 自动上传脚本

> 后端已内置进程管理，会在应用生命周期中尝试启动 `python/main.py`。  
> 你也可以手动运行用于调试。

手动运行：

```powershell
cd python
python main.py --watch-dir ../backend/detected_frames --endpoint http://127.0.0.1:8000/api/script/detect-fire
```

上传工具（单张/多张）：

```powershell
python upload_image.py .\fire.jpg --endpoint http://127.0.0.1:8000/api/script/detect-fire
```

## 7. YOLO 脚本说明（可选）

`python/yolo.py` 用于本地摄像头检测，并将检测帧写入 `backend/detected_frames`。  

### 如何使用：
0. 配置好YOLO所需的环境
1. 下载yolo源码（8.4.14）
2. 将源码解压到与此项目同一个目录下
3. 复制python文件夹中的yolo.py与fire_test.pt到ultralytics-8.4.1文件夹中
4. 直接运行yolo.py即可
  
例如：
```text
test
|-- fire_detection/
`-- ultralytics-8.4.14/
   |-- fire_test.pt
   `-- yolo.py
```

## 8. API 概览

### 检测相关
- `POST /api/manual/detect-fire`  
  上传字段：`file`（image/*）
- `POST /api/script/detect-fire`  
  上传字段：`file`（image/*）
- `GET /api/health/script-uploader`  
  查看自动上传进程状态
- `WS /ws/script/latest-upload-image`  
  接收自动上传最新结果推送

### 数据监控
- `GET /api/data-monitor/records?sort_by=created_at&sort_order=desc`
- `POST /api/data-monitor/records`
  - `scene_image`（jpg）
  - `remark`（可选）
- `PUT /api/data-monitor/records/{record_id}`
  - `scene_image`（可选）
  - `remark`（可选）
- `DELETE /api/data-monitor/records/{record_id}`

## 9. 目录与静态资源约定

- `backend/detected_frames`  
  自动上传监听目录（会在后端启动和关闭时清空）
- `backend/data_image`  
  数据监控记录图片存储目录
- 前端访问监控图片 URL：`/static/data-image/<filename>`

## 10. 常见问题

### 10.1 Qwen 调用失败
- 检查 `QWEN_API_KEY` 是否正确
- 检查 `QWEN_BASE_URL` 是否可访问
- 检查模型名 `QWEN_MODEL`

### 10.2 数据库连接失败
- 检查 `MYSQL_URL` 或 `MYSQL_HOST/PORT/USER/PASSWORD`
- 确认数据库已创建，账号有建表权限

### 10.3 监控图片不显示
- 检查 `backend/data_image` 是否有文件
- 检查后端静态挂载 `/static/data-image`
- 检查前端 `VITE_API_BASE` 是否指向正确后端地址

## 11. 开发建议

- 后端优先使用 `backend/.env.example` 复制出 `.env`
- 前端优先使用 `frontend/.env.example` 复制出 `.env`
- 若历史 `monitor_records` 表结构不一致，可使用：

```powershell
cd backend
python scripts/rebuild_monitor_records.py
```
