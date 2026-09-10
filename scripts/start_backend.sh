#!/bin/bash
# Launch uvicorn in a fully detached way
pkill -f "uvicorn app.main" 2>/dev/null
sleep 2
unset DATABASE_URL
cd /home/z/my-project/backend
source venv/bin/activate
setsid nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/uvicorn.log 2>&1 < /dev/null &
echo "Launched uvicorn, PID=$!"
disown
sleep 10
echo "=== uvicorn log ==="
cat /tmp/uvicorn.log
echo ""
echo "=== / endpoint ==="
curl -s http://localhost:8000/
echo ""
