#!/bin/bash
# Deploy Agent Claud to Oracle Cloud Free Tier
# Run this on your Ubuntu server via SSH

set -e

echo "=== Agent Claud - Deploy ==="

# 1. System deps
sudo apt update && sudo apt install -y python3 python3-pip python3-venv git

# 2. Project dir
APP_DIR="/opt/agent-claud"
sudo mkdir -p $APP_DIR
sudo chown $USER:$USER $APP_DIR

# 3. Copy project files (run from project dir on your PC first)
# scp -r ./* user@server:/opt/agent-claud/

# 4. Python env
cd $APP_DIR
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 5. Ollama (for AI)
curl -fsSL https://ollama.ai/install.sh | sh
ollama pull llama3.2

# 6. Systemd service
sudo tee /etc/systemd/system/agent-claud.service > /dev/null <<EOF
[Unit]
Description=Agent Claud Telegram Bot
After=network.target ollama.service

[Service]
Type=simple
User=$USER
WorkingDirectory=$APP_DIR
Environment=PATH=$APP_DIR/venv/bin
ExecStart=$APP_DIR/venv/bin/python bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 7. Start
sudo systemctl daemon-reload
sudo systemctl enable agent-claud
sudo systemctl start agent-claud

echo "=== Done! Bot is running 24/7 ==="
echo "Check: sudo systemctl status agent-claud"
echo "Logs:  sudo journalctl -u agent-claud -f"
