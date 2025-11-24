#!/bin/bash
set -e

# Configuration
APP_DIR="/opt/second_brain_database"
USER="sbd"
GROUP="sbd"
REPO_URL="https://github.com/rohanbatrain/second_brain_database.git"

echo "🚀 Starting Bare Metal Deployment..."

# 1. System Dependencies
echo "📦 Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv git curl ffmpeg portaudio19-dev

# 2. User Setup
if ! id "$USER" &>/dev/null; then
    echo "👤 Creating user $USER..."
    sudo useradd -r -s /bin/false $USER
fi

# 3. Application Setup
if [ ! -d "$APP_DIR" ]; then
    echo "📂 Cloning repository..."
    sudo git clone $REPO_URL $APP_DIR
    sudo chown -R $USER:$GROUP $APP_DIR
else
    echo "🔄 Updating repository..."
    cd $APP_DIR
    sudo -u $USER git pull
fi

# 4. Python Environment (using uv)
echo "🐍 Setting up Python environment..."
if ! command -v uv &> /dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="/root/.cargo/bin:$PATH"
fi

cd $APP_DIR
sudo -u $USER uv sync --frozen --no-dev --extra voice

# 5. Systemd Service
echo "⚙️ Configuring Systemd service..."
sudo tee /etc/systemd/system/sbd.service > /dev/null <<EOF
[Unit]
Description=Second Brain Database API
After=network.target

[Service]
User=$USER
Group=$GROUP
WorkingDirectory=$APP_DIR
EnvironmentFile=$APP_DIR/.env
ExecStart=/home/$USER/.cargo/bin/uv run uvicorn src.second_brain_database.main:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable sbd

echo "✅ Deployment setup complete!"
echo "📝 Next steps:"
echo "1. Create .env file in $APP_DIR"
echo "2. Start service: sudo systemctl start sbd"
