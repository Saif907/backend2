# Trading Journal Backend

FastAPI backend for AI-powered trading journal application.

## Features

- 🔐 User authentication with Supabase
- 💬 Chat sessions with AI assistant
- 📊 Trade logging and management
- 🤖 AI-powered trade extraction from natural language
- 📈 Analytics and insights generation
- 🔒 Secure JWT token-based authentication

## Tech Stack

- **FastAPI** - Modern web framework
- **Supabase** - Database and authentication
- **Anthropic Claude** - AI/LLM integration
- **PostgreSQL** - Database (via Supabase)

## Setup

### 1. Install Dependencies

```bash
chmod +x install.sh
./install.sh
```

### 2. Configure Environment

Edit `.env` file with your credentials:

```env
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_anon_key
SUPABASE_SERVICE_KEY=your_service_role_key
SECRET_KEY=generate_with_openssl_rand_hex_32
ANTHROPIC_API_KEY=your_claude_api_key
```

### 3. Create Empty __init__.py Files

```bash
touch app/__init__.py
touch app/apis/__init__.py
touch app/auth/__init__.py
touch app/libs/__init__.py
```

### 4. Start Server

```bash
chmod +x run.sh
./run.sh
```

Server will run on `http://localhost:8000`

## API Documentation

Visit `http://localhost:8000/docs` for interactive API documentation.

## Project Structure

```
backend/
├── app/
│   ├── apis/           # API endpoints
│   │   ├── ai_router.py
│   │   ├── chat_router.py
│   │   ├── trade_router.py
│   │   └── models.py
│   ├── auth/           # Authentication
│   │   ├── router.py
│   │   ├── utils.py
│   │   └── models.py
│   └── libs/           # Core utilities
│       ├── config.py
│       ├── supabase_client.py
│       └── ai_service.py
├── main.py             # App entry point
├── requirements.txt    # Dependencies
├── .env               # Environment variables
└── README.md          # Documentation
```

## API Endpoints

### Authentication
- `POST /api/auth/signup` - Register new user
- `POST /api/auth/signin` - Login user
- `POST /api/auth/signout` - Logout user
- `GET /api/auth/me` - Get current user

### Chats
- `POST /api/chats` - Create new chat
- `GET /api/chats` - Get all chats
- `GET /api/chats/{id}` - Get chat with messages
- `DELETE /api/chats/{id}` - Delete chat
- `POST /api/chats/messages` - Create message

### Trades
- `POST /api/trades` - Create trade
- `GET /api/trades` - Get all trades
- `GET /api/trades/{id}` - Get specific trade
- `PATCH /api/trades/{id}` - Update trade
- `DELETE /api/trades/{id}` - Delete trade

### AI
- `POST /api/ai/chat` - Send message to AI
- `POST /api/ai/extract-trade` - Extract trade from text
- `POST /api/ai/analytics` - Get analytics
- `GET /api/ai/insights` - Get AI insights

## Development

### Run in Development Mode

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Install New Dependencies

```bash
source venv/bin/activate
pip install package_name
pip freeze > requirements.txt
```

## License

MIT