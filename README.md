# Ananya Telegram Bot

<div align="center">

![Python Version](https://img.shields.io/badge/python-3.11+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Docker](https://img.shields.io/badge/docker-ready-brightgreen.svg)
![Status](https://img.shields.io/badge/status-production--ready-success.svg)

**AI-powered Telegram bot with FastAPI web admin panel, personality management, and Gemini AI integration**

[Features](#features) • [Quick Start](#quick-start) • [Deploy](#one-click-deployment) • [Documentation](#documentation) • [API](#api-endpoints)

</div>

---

## 🚀 One-Click Deployment

Deploy instantly to your favorite platform:

<div align="center">

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/paman7647/ananya-bot)

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template/ananya-bot?referralCode=paman7647)

[![Deploy to Heroku](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy?template=https://github.com/paman7647/ananya-bot)

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https://github.com/paman7647/ananya-bot)

[![Deploy to DO](https://www.deploytodo.com/do-btn-blue.svg)](https://cloud.digitalocean.com/apps/new?repo=https://github.com/paman7647/ananya-bot/tree/main)

[![Deploy to Azure](https://aka.ms/deploytoazurebutton)](https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2Fpaman7647%2Fananya-bot%2Fmain%2Fazure-container-app.yaml)

</div>

### Other Platforms

```bash
# Fly.io
fly launch --from https://github.com/paman7647/ananya-bot

# Google Cloud Run
gcloud run deploy --source https://github.com/paman7647/ananya-bot

# AWS (via Kubernetes)
kubectl apply -f https://raw.githubusercontent.com/paman7647/ananya-bot/main/k8s-deployment.yaml
```

---
- 🤖 **AI Chat**: Powered by Google Gemini 2.5 Flash
- 🎨 **Multi-modal**: Supports text, images, voice, and documents
- 🔍 **Smart Search**: Automatic Google Search integration
- 👑 **Admin Panel**: Complete user and bot management
- 🎭 **Personality System**: Multiple AI personalities (Default, Spiritual, Nationalist)
- 📊 **Statistics**: User analytics and bot metrics
- 📢 **Broadcast**: Send messages to all users
- 🔧 **Advanced Tools**: System monitoring, cache clearing, bot restart
- 🌐 **Web App Ready**: Health checks and containerized deployment
- 🔒 **Security**: Environment-based configuration, no hardcoded secrets
- 🏥 **Health Monitoring**: Comprehensive health checks and system monitoring
- 🛡️ **Input Validation**: Sanitized inputs and error handling


## 🎯 Quick Start

### Prerequisites

| Requirement | Version | Get It |
|------------|---------|---------|
| Python | 3.11+ | [Download](https://www.python.org/downloads/) |
| MongoDB | 6.0+ | [Download](https://www.mongodb.com/try/download/community) |
| Telegram Bot Token | - | [@BotFather](https://t.me/botfather) |
| Telegram API | - | [my.telegram.org](https://my.telegram.org) |
| Gemini API Key | - | [AI Studio](https://aistudio.google.com) |

### 🔧 Local Development

**1. Clone & Setup**
```bash
git clone https://github.com/paman7647/ananya-bot.git
cd ananya-bot
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

**2. Configure Environment**
```bash
cp .env.example .env
nano .env  # Edit with your credentials
```

**3. Run Application**
```bash
# Start everything
./start.sh all

# Or start services separately
python -m src.bot.main        # Telegram bot only
python -m src.web.run          # Web panel only
```

**4. Access Dashboard**
```
🌐 http://localhost:8080
```

---

## 🐳 Docker Deployment

### Local Docker
```bash
# Build and run
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Production Docker
```bash
# Use cloud configuration
docker-compose -f docker-compose.cloud.yml up -d
```

---

## ⚙️ Configuration

### Docker Deployment

```bash
# Build and run with Docker Compose
docker-compose up -d

# Or build manually
docker build -t ananya-bot .
docker run -d --env-file .env ananya-bot
```

## 🔧 Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather | Yes |
| `API_ID` | Telegram API ID | Yes |
| `API_HASH` | Telegram API Hash | Yes |
| `GEMINI_API_KEY` | Google Gemini API Key | Yes |
| `MONGODB_URI` | MongoDB connection string | Yes |
| `ADMIN_USER_ID` | Telegram user ID of admin | Yes |
| `ADMIN_TOKEN` | Secure token for API access | Yes |
| `SECRET_KEY` | Flask/Django-style secret key | Yes |
| `SESSION_SECRET` | Session encryption secret | Yes |
| `PORT` | Web server port (default: 8080) | No |
| `LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) | No |

### Security Notes

- **Never commit `.env` file** to version control
- Use strong, unique secrets for `SECRET_KEY` and `SESSION_SECRET`
- Rotate API keys regularly
- Use environment-specific MongoDB databases

## 🏥 Health Checks

The application provides comprehensive health monitoring:

### Basic Health Check
```
GET /health
```
Returns basic service status.

### Detailed Health Check
```
GET /health/detailed
```
Returns system resources, database status, and bot status.

### API Status
```
GET /api/status
```
Returns API connectivity status for external monitoring.

## 🌐 Platform Deployments

### Heroku

1. Create a new Heroku app
2. Set environment variables in Heroku dashboard
3. Deploy using Heroku CLI:
   ```bash
   heroku create your-app-name
   heroku config:set TELEGRAM_BOT_TOKEN=your_token
   heroku config:set GEMINI_API_KEY=your_key
   # ... set other variables
   git push heroku main
   ```

### Railway

1. Connect your GitHub repository
2. Add environment variables in Railway dashboard
3. Deploy automatically

### Render

1. Create a new Web Service
2. Connect your repository
3. Set environment variables
4. Set build command: `pip install -r requirements.txt`
5. Set start command: `python3 new.py`

### VPS/Cloud Server

```bash
# Install dependencies
sudo apt update
sudo apt install python3 python3-pip

# Clone and setup
git clone <your-repo>
cd ananya-bot
pip install -r requirements.txt

# Create systemd service
sudo nano /etc/systemd/system/ananya-bot.service
```

Add this content:
```ini
[Unit]
Description=Ananya Telegram Bot
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/ananya-bot
ExecStart=/usr/bin/python3 new.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start service
sudo systemctl enable ananya-bot
sudo systemctl start ananya-bot
sudo systemctl status ananya-bot
```

## 🔧 Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `TELEGRAM_BOT_TOKEN` | Your Telegram bot token from @BotFather | ✅ |
| `API_ID` | Telegram API ID | ✅ |
| `API_HASH` | Telegram API Hash | ✅ |
| `GEMINI_API_KEY` | Google Gemini API key | ✅ |
| `MONGODB_URI` | MongoDB connection string | ✅ |
| `DATABASE_NAME` | Database name (default: telegram_bot) | ❌ |
| `ENABLE_HEALTH_CHECK` | Enable health check server (default: false) | ❌ |
| `PORT` | Health check server port (default: 8080) | ❌ |

## 📊 Health Checks

When `ENABLE_HEALTH_CHECK=true`, the bot exposes a health check endpoint at `http://localhost:8080/health` that returns:

```json
{
  "status": "healthy",
  "timestamp": "2025-01-04T10:30:00"
}
```

## 🛠️ Admin Commands

- `/admin` - Open admin panel
- `/settings` or `/menu` - Open user settings

## 🎭 Personalities

- **Default**: Friendly and helpful AI assistant
- **Spiritual**: Wisdom from Hindu scriptures
- **Nationalist**: Proud Indian perspective

## 📈 Monitoring

The bot includes comprehensive logging and error handling. Check logs with:
```bash
docker-compose logs -f ananya-bot
```

## 🔒 Security

- Environment variables for sensitive data
- Input validation and sanitization
- Rate limiting and flood protection
- Admin authentication system

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

If you encounter issues:
1. Check the logs: `docker-compose logs ananya-bot`
2. Verify environment variables are set correctly
3. Ensure all dependencies are installed
4. Check MongoDB connection

For bot-related issues, make sure your Telegram bot token and API credentials are valid.
```

## User Interface

### User Commands
- `/settings` or `/menu` - Open user settings menu
- Send any message - Chat with AI
- Send photos, voice messages, or documents - Multi-modal chat

### User Menu Features
- 🤖 **Change Personality**: Select from available AI personalities
- 📊 **My Statistics**: View personal chat statistics
- 🗑️ **Clear History**: Delete all chat history
- ℹ️ **Help**: View bot features and help

## Admin Interface

Access the admin panel by sending `/admin` in a private chat.

### Admin Panel Sections

#### 👥 User Management
- 📋 **List Users**: View all users with details
- 🔍 **Search User**: Find users by name/username
- 🚫 **Block User**: Block users from using the bot
- ✅ **Unblock User**: Restore access to blocked users
- 📊 **User Stats**: Detailed user analytics

#### 🤖 Personality Management
- ➕ **Add Personality**: Create new AI personalities
- 📋 **List Personalities**: View all available personalities
- ✏️ **Edit Personality**: Modify existing personalities
- 🗑️ **Delete Personality**: Remove personalities

#### 👑 Admin Management
- ➕ **Add Admin**: Promote users to admin
- 📋 **List Admins**: View all administrators
- 🗑️ **Remove Admin**: Demote administrators

#### 📢 Broadcast
- 📢 **Broadcast Message**: Send messages to all users
- 📊 **Broadcast Stats**: View broadcast history and analytics

#### 🔧 Advanced Tools
- 🔄 **Restart Bot**: Restart the bot (with confirmation)
- 📊 **System Info**: View system resources and bot status
- 🗃️ **Database Backup**: Create full database backup
- 🧹 **Clear Cache**: Clear bot cache

#### 📊 Statistics
- 👥 Total Users, Active Users (7d), Total Chats
- 🚫 Blocked Users count
- Real-time statistics with refresh option

## Google Search Integration

The bot automatically detects when a query would benefit from Google Search and enables the grounding tool. This happens for queries containing keywords like:
- search, google, find, lookup
- what is, who is, how to
- current, latest, news, weather
- price, cost

## Multi-modal Support

The bot can process:
- 📷 **Images**: JPEG photos for visual analysis
- 🎵 **Voice Messages**: OGG audio for transcription
- 📄 **Documents**: Various file types for analysis

## Database Collections

- `users`: User information, settings, personalities, activity tracking
- `chats`: Chat history and conversations with media support
- `admins`: Administrator privileges and management
- `personalities`: Custom AI personality definitions

## Menu Structure

All menus follow a consistent structure:
- **Main menus** have 4-6 primary options
- **Sub-menus** include action buttons and a "Back" button
- **Confirmation dialogs** for destructive actions
- **Consistent button layout** and emoji usage
- **Proper navigation** between all menu levels

## Security Features

- Admin authentication required for admin functions
- User blocking system with persistent storage
- Input validation and error handling
- Safe database operations with error recovery

## Dependencies

- `telethon>=1.28.0`: Telegram API client
- `pymongo>=4.3.0`: MongoDB driver
- `google-genai>=0.1.0`: Google Gemini AI client
- `python-dotenv>=1.0.0`: Environment variable management
- `psutil>=5.9.0`: System monitoring (optional)

## File Structure

```
/
├── new.py              # Main bot application
├── requirements.txt    # Python dependencies
├── README.md          # This documentation
├── .env               # Environment variables (create this)
└── backups/           # Database backup directory (auto-created)
```

## Notes

- All admin functions use inline buttons only (no text commands)
- Messages longer than 4000 characters are automatically chunked
- Chat history is maintained for context (last 10 messages)
- Automatic user activity tracking and statistics
- Database backups are saved in JSON format
- System monitoring requires `psutil` package


## ✨ Features

<table>
<tr>
<td width="50%">

### 🤖 AI & Automation
- **Google Gemini AI** - Natural language processing
- **Multiple Personalities** - Default, Spiritual, Nationalist
- **Voice Messages** - Multi-engine TTS support
- **Auto-responses** - Context-aware replies
- **Language Detection** - Multi-language support

</td>
<td width="50%">

### 🎛️ Management & Control
- **Web Admin Panel** - FastAPI dashboard
- **Real-time Stats** - WebSocket monitoring
- **User Management** - Block/unblock users
- **Broadcast System** - Mass messaging
- **Personality Manager** - Dynamic AI personalities

</td>
</tr>
<tr>
<td width="50%">

### � Security & Auth
- **Secure Authentication** - Session-based login
- **Admin Controls** - Role-based access
- **Environment Config** - Secure secrets management
- **Rate Limiting** - Anti-spam protection
- **Audit Logging** - Complete activity logs

</td>
<td width="50%">

### 🚀 Deployment & Scale
- **Docker Ready** - Containerized deployment
- **Multi-Cloud** - 10+ platform support
- **Auto-scaling** - Handle traffic spikes
- **Health Checks** - Built-in monitoring
- **CI/CD Ready** - GitHub Actions

</td>
</tr>
</table>

---

## 📸 Screenshots

<div align="center">

| Web Admin Panel | Bot Conversation |
|:---:|:---:|
| ![Dashboard](https://via.placeholder.com/400x300?text=Web+Admin+Dashboard) | ![Chat](https://via.placeholder.com/400x300?text=Telegram+Bot+Chat) |

</div>

---

## Setup

### 1. Environment Variables

Create a `.env` file in the project root:

```env
API_ID=your_telegram_api_id
API_HASH=your_telegram_api_hash
BOT_TOKEN=your_bot_token
GEMINI_API_KEY=your_gemini_api_key
MONGO_URI=mongodb://localhost:27017
DATABASE_NAME=telegram_bot
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. MongoDB Setup

Make sure MongoDB is running locally or update `MONGO_URI` for your MongoDB instance.

### 4. Run the Bot

```bash
python new.py
```

## Admin Panel

Access the admin panel by sending `/admin` in a private chat with the bot.

### Available Admin Functions:

- **User Management**: List, search, block/unblock users
- **Personality Management**: Add, edit, delete AI personalities
- **Admin Management**: Add/remove bot administrators
- **Broadcast**: Send messages to all users
- **Advanced Tools**: System maintenance and monitoring
- **Statistics**: View bot usage statistics

## Google Search Integration

The bot automatically detects when a query would benefit from Google Search and enables the grounding tool. This happens for queries containing keywords like:
- search, google, find, lookup
- what is, who is, how to
- current, latest, news, weather
- price, cost

## Multi-modal Support

The bot can process:
- **Images**: JPEG photos
- **Voice Messages**: OGG audio
- **Documents**: Various file types

## Database Collections

- `users`: User information and settings
- `chats`: Chat history and conversations
- `admins`: Administrator privileges
- `personalities`: Custom AI personalities

## Security

- Admin authentication required for all admin functions
- User blocking system
- Input validation and error handling

## Dependencies

- `telethon`: Telegram API client
- `pymongo`: MongoDB driver
- `google-genai`: Google Gemini AI client
- `python-dotenv`: Environment variable management

## Notes

- All admin functions use inline buttons (no text commands)
- Messages longer than 4000 characters are automatically chunked
- Chat history is maintained for context (last 10 messages)
- Automatic user activity tracking