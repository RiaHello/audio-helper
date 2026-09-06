# 语音约碰面地点

按住说话，为同一座城市里的两个人推荐中间附近的店铺。第一版默认城市为杭州。

## 环境

- Python 3.11
- Node.js 22.12 及以上的 22.x
- 后端 `http://localhost:8003`
- 前端 `http://localhost:5175`

密钥填入 `backend/.env`。仓库只保留 `backend/.env.example` 空值模板。未填写密钥时，健康检查仍应可用。

## 启动

后端：

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python main.py
```

前端：

```bash
cd frontend
npm install
npm run dev
```

## 本轮可验证内容

- 浏览器打开 `http://localhost:5175`，应看到基础页面。
- 浏览器打开 `http://localhost:8003/health` 或 `http://localhost:8003/docs` 调用 `GET /health`。
- 预期状态码 `200`，响应形如 `{"request_id": "...", "data": {"status": "ok"}}`。

录音、识别、找店等业务接口尚未实现。
