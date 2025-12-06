# Masumi Service

A simple Masumi-compliant service for payments and identity on the Masumi Network.

## Overview

This project provides a minimal wrapper for creating Masumi-compliant API services. It handles job processing, payment integration, and agent registration with the Masumi Network.

## Prerequisites

- Python 3.8 or higher
- Blockfrost API key (for Cardano blockchain interactions)
- Masumi Payment Service instance (deploy via Railway template)
- Railway account (optional, for deployment)

## Setup

1. **Clone or navigate to this project:**
   ```bash
   cd clausehaus
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables:**
   ```bash
   cp env.example .env
   ```
   
   Edit `.env` and set the following:
   - `PAYMENT_SERVICE_URL`: URL of your Masumi Payment Service
   - `PAYMENT_API_KEY`: Admin key from your Masumi Payment Service
   - `SELLER_VKEY`: Found in the admin panel under your selling wallet
   - `LLM_PROVIDER`: LLM provider (e.g., "openai", "anthropic")
   - `LLM_API_KEY`: API key for your LLM provider
   - `LLM_MODEL`: Model name (e.g., "gpt-4", "claude-3-opus-20240229")

## Running the Service

**Development mode:**
```bash
python main.py
```

**Production mode with uvicorn:**
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The service will be available at:
- API: `http://localhost:8000`
- API Documentation: `http://localhost:8000/docs`
- Health Check: `http://localhost:8000/api/v1/health`

## API Endpoints

### `GET /api/v1/`
Health check endpoint.

### `POST /api/v1/jobs`
Create a new job and start processing it.

**Request:**
```json
{
  "input_data": {
    "prompt": "Your prompt to the LLM",
    "system_prompt": "Optional system prompt"
  },
  "payment_id": "optional_payment_id"
}
```

**Response:**
```json
{
  "job_id": "uuid",
  "payment_id": "optional_payment_id",
  "status": "processing"
}
```

### `GET /api/v1/jobs/{job_id}`
Get the status of a job.

**Response:**
```json
{
  "job_id": "uuid",
  "status": "completed",
  "result": {
    "output": "processed result"
  },
  "error": null
}
```

### `POST /api/v1/jobs/purchase`
Handle payment for a completed job (called by Masumi Payment Service).

### `GET /api/v1/health`
Detailed health check with configuration status.

## Customizing Job Processing

The job service is implemented in `app/services/job_service.py`. The `process_job` method is currently a TODO placeholder where you can implement your custom job processing logic.

### Request Format

Jobs expect `input_data` as an array of key-value pairs:
```json
{
  "input_data": [
    {"key": "task", "value": "your task description"},
    {"key": "param1", "value": "value1"}
  ],
  "payment_id": "optional_payment_id"
}
```

## Deployment

### Railway Deployment

1. Connect your repository to Railway
2. Set environment variables in Railway dashboard
3. Deploy the service
4. Get the public URL for your agent service

### Register Agent on Masumi

1. Top up your selling wallet using the Masumi tADA dispenser
2. Register the agent via the Agent Service URL
3. Retrieve the Agent ID (Asset ID)

## Testing

1. **Start a job:**
   ```bash
   curl -X POST http://localhost:8000/api/v1/jobs \
     -H "Content-Type: application/json" \
     -d '{"input_data": {"prompt": "What is the capital of France?"}}'
   ```

2. **Check job status:**
   ```bash
   curl http://localhost:8000/api/v1/jobs/{job_id}
   ```

3. **Test payment flow:**
   - Complete a job
   - Copy the job output (excluding `job_id` and `payment_id`)
   - Send POST request to `/purchase` endpoint on Masumi Payment Service

## Project Structure

This project follows FastAPI best practices with a modular structure:

```
clausehaus/
├── app/
│   ├── main.py              # FastAPI application initialization
│   ├── api/                 # API routes
│   │   └── v1/              # API version 1
│   │       ├── router.py    # API router configuration
│   │       ├── jobs.py      # Job-related endpoints
│   │       └── health.py   # Health check endpoints
│   ├── core/                # Core configuration
│   │   └── config.py        # Application settings
│   ├── schemas/             # Pydantic models
│   │   └── job.py           # Job-related schemas
│   ├── services/            # Business logic
│   │   ├── job_service.py      # Job processing
│   │   └── payment_service.py  # Payment integration
│   └── db/                  # Database (for future use)
│       └── base.py          # Database base configuration
├── main.py                  # Application entry point
├── requirements.txt         # Python dependencies
├── env.example              # Environment variables template
├── .gitignore              # Git ignore file
└── README.md               # This file
```

## Next Steps

- Replace in-memory job storage with a database (PostgreSQL, MongoDB, etc.)
- Add support for additional LLM providers
- Add authentication and authorization
- Implement proper error handling and retries
- Add logging and monitoring
- Set up CI/CD pipeline
- Add streaming support for LLM responses

## Resources

- [Masumi Network Documentation](https://masumi.network)
- [Masumi Service Wrapper Repository](https://github.com/masumi-network/agentic-service-wrapper)
- [Masumi Payment Service](https://railway.app/template/masumi-payment-service)

## License

MIT

