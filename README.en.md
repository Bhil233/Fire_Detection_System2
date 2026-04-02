# AI Fire Detection and Monitoring System

This project is a full-stack fire detection system built with `FastAPI + Vue 3 + Qwen-VL + MySQL`.

It supports:
- Manual image upload detection
- Script-based automatic image upload detection (folder watcher)
- Monitoring records management (CRUD + sorting)
- Auto-creation of monitoring records after each detection

## 1. Project Structure

```text
fire_detection/
|-- backend/                      # FastAPI backend
|   |-- app_factory.py            # app lifecycle, static mounts
|   |-- config.py                 # env config
|   |-- database.py               # async SQLAlchemy setup
|   |-- main.py                   # FastAPI entry
|   |-- routers/
|   |   |-- detect.py             # detection APIs + websocket
|   |   `-- data_monitor.py       # monitor record CRUD + sorting
|   |-- services/
|   |   |-- qwen_client.py        # Qwen API client
|   |   |-- monitor_records.py    # monitor record/image storage service
|   |   `-- script_uploader.py    # auto uploader process manager
|   |-- models/
|   |-- scripts/rebuild_monitor_records.py
|   |-- detected_frames/          # watcher input dir (script side)
|   |-- data_image/               # monitor image dir (DB records use this)
|   `-- requirements.txt
|-- frontend/                     # Vue 3 + Vite frontend
|   |-- src/
|   |   |-- App.vue
|   |   |-- components/
|   |   |-- services/fireApi.js
|   |   |-- composables/useScriptSocket.js
|   |   |-- utils/format.js
|   |   `-- config/api.js
|   `-- package.json
`-- python/                       # local uploader + YOLO scripts
    |-- main.py
    |-- upload_image.py
    `-- yolo.py
```

## 2. Key Workflows

### 2.1 Manual detection
1. Frontend uploads an image to `POST /api/manual/detect-fire`
2. Backend calls Qwen for fire detection
3. Backend auto-creates a monitor record and saves the image to `backend/data_image`
4. Backend returns detection result and `monitor_record`

### 2.2 Script-based automatic detection
1. `python/main.py` watches `backend/detected_frames`
2. New files are uploaded to `POST /api/script/detect-fire`
3. Backend detects fire and auto-creates monitor records
4. Backend broadcasts latest script result through WebSocket `/ws/script/latest-upload-image`

### 2.3 Data monitor module
- List API: `GET /api/data-monitor/records`
- Sorting params:
  - `sort_by`: `id | status | remark | created_at | updated_at | time`
  - `sort_order`: `asc | desc`
- Full CRUD for monitor records

## 3. Environment Requirements

- Python `3.10+` (recommended)
- Node.js `18+`
- MySQL `8+` (or compatible)

## 4. Backend Setup

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Run backend:

```powershell
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Default backend URL: `http://127.0.0.1:8000`

## 5. Frontend Setup

```powershell
cd frontend
npm install
copy .env.example .env
npm run dev
```

Default frontend URL: `http://127.0.0.1:5173`

## 6. Important Environment Variables

From `backend/.env.example`:

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

From `frontend/.env.example`:

```env
VITE_API_BASE=http://127.0.0.1:8000
```

## 7. API Summary

### Detection
- `POST /api/manual/detect-fire`
- `POST /api/script/detect-fire`
- `GET /api/health/script-uploader`
- `WS /ws/script/latest-upload-image`

### Data monitor
- `GET /api/data-monitor/records?sort_by=created_at&sort_order=desc`
- `POST /api/data-monitor/records`
- `PUT /api/data-monitor/records/{record_id}`
- `DELETE /api/data-monitor/records/{record_id}`

## 8. Current Behavior Notes (Latest Changes)

- Monitor images are stored under `backend/data_image` (not `backend/detected_frames`)
- Backend mounts monitor images at `/static/data-image/...`
- `backend/detected_frames` is auto-cleared on backend startup and shutdown
- Data monitor list supports sorting by `id`, `status`, `remark`, and time fields
- Frontend status display in monitor table:
  - `发生火灾` -> red and bold
  - `无火灾` -> green

## 9. Python Scripts

Manual run for folder watcher uploader:

```powershell
cd python
python main.py --watch-dir ../backend/detected_frames --endpoint http://127.0.0.1:8000/api/script/detect-fire
```

Upload helper:

```powershell
python upload_image.py .\fire.jpg --endpoint http://127.0.0.1:8000/api/script/detect-fire
```

`python/yolo.py` requires extra dependencies (not in backend requirements):
- `ultralytics`
- `opencv-python`
- local model file (`fire_test.pt` by default in script)

## 10. Troubleshooting

### Qwen call fails
- Check `QWEN_API_KEY`
- Check `QWEN_BASE_URL`
- Check `QWEN_MODEL`

### Database connection fails
- Verify `MYSQL_URL` or `MYSQL_HOST/PORT/USER/PASSWORD`
- Ensure DB exists and user has table permissions

### Monitor image not shown
- Verify files exist in `backend/data_image`
- Verify backend static route `/static/data-image`
- Verify frontend `VITE_API_BASE` points to the correct backend
