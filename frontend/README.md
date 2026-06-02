# frontend

React + Vite UI for AITeacher.

```bash
npm install
npm run dev   # http://localhost:5173 (proxies /api -> http://localhost:8000)
npm test      # vitest
```

If you see `POST /api/auth/login 500` and Vite logs `connect ECONNREFUSED ::1:8000`, start the backend with IPv6 enabled (e.g. `uvicorn ... --host :: --port 8000`) so the proxy can reach it.
