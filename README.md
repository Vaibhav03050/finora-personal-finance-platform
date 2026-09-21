# Finora — Personal Finance & Goal Planning Platform

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Python](https://img.shields.io/badge/Python-3.12-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115.6-009688.svg)
![Docker](https://img.shields.io/badge/Docker-supported-2496ED.svg)

> **Understand your money. Plan with confidence. Build better habits.**

Finora is a personal finance web application that helps users record and review transactions, import bank-statement data, understand spending patterns, plan financial goals, and explore beginner-friendly financial concepts.
The application combines a FastAPI backend with a lightweight HTML, CSS, and JavaScript frontend. It supports local SQLite storage, optional AI-assisted coaching, OCR-based document processing, transaction categorization, analytics, and Docker-based execution.

## Features

- **User authentication** with account-level access controls and JWT-based sessions.
- **Personalized onboarding** with manual financial-profile entry and beginner-friendly estimates.
- **Transaction management** for creating, viewing, editing, filtering, and deleting income and expense records.
- **Transaction import** through CSV bank exports, bank-statement PDFs, and statement or receipt images.
- **Review-before-confirmation workflow** for imported transaction rows before they are saved to the ledger.
- **Transaction categorization** using deterministic keyword rules with a TF-IDF and Logistic Regression fallback for unfamiliar descriptions.
- **Spending analytics** covering income, expenses, savings, categories, and trends.
- **Financial Health Score** with an explainable breakdown based on savings rate, expense-to-income ratio, emergency savings, and debt/EMI burden.
- **Savings suggestions** based on spending categories and observed trends.
- **Financial goals** with progress tracking, target dates, and monthly saving guidance.
- **AI Money Coach** that uses financial context from the user's data and supports an optional external AI provider; a deterministic fallback is available when no provider is configured.
- **Financial education** covering saving, budgeting, emergency funds, compounding, SIPs, mutual funds, fixed deposits, risk, diversification, and related concepts.
- **Investment simulator** for illustrative compound-growth calculations and educational investment comparisons.
- **Security-oriented safeguards** including upload validation, request rate limiting, security headers, protected routes, and audit logging for selected account actions.

## Screenshots

| Dashboard | Transactions |
|---|---|
| ![Dashboard](screenshots/dashboard.png) | ![Transactions](screenshots/transactions.png) |

| Statement / Data Upload | Goals |
|---|---|
| ![Upload](screenshots/upload.png) | ![Goals](screenshots/goals.png) |

| Savings Plan |
|---|
| ![Savings Plan](screenshots/saving-plan.png) |

## Tech Stack

### Backend

- Python 3.12
- FastAPI
- SQLModel
- SQLite
- Pydantic Settings
- JWT authentication with `python-jose`
- Pandas and NumPy
- Scikit-learn and Joblib
- Pillow and Tesseract OCR
- PyMuPDF for PDF processing
- Pytest for automated tests

### Frontend

- HTML
- CSS
- Vanilla JavaScript
- Hash-based client-side navigation
- Responsive interface served by the FastAPI application

### DevOps and Runtime

- Docker
- Docker Compose
- Persistent Docker volume for SQLite data
- Uvicorn application server

## Project Structure

```text
finora/
├── backend/
│   ├── app/
│   │   ├── routers/
│   │   │   ├── admin.py
│   │   │   ├── analytics.py
│   │   │   ├── assistant.py
│   │   │   ├── auth.py
│   │   │   ├── education.py
│   │   │   ├── goals.py
│   │   │   ├── profile.py
│   │   │   ├── simulator.py
│   │   │   ├── transactions.py
│   │   │   └── uploads.py
│   │   ├── services/
│   │   ├── ml/
│   │   │   └── categorizer.joblib
│   │   ├── main.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── database.py
│   │   ├── auth.py
│   │   ├── config.py
│   │   └── rate_limit.py
│   ├── tests/
│   └── requirements.txt
├── frontend/
│   ├── templates/
│   └── static/
├── screenshots/
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── .gitignore
├── LICENSE
└── README.md
```

## Getting Started

### Prerequisites

- Python 3.12
- Git
- Optional: Docker Desktop for containerized execution
- Tesseract OCR for local image OCR processing when running outside Docker

### 1. Clone the repository

```bash
git clone https://github.com/Vaibhav03050/finora-personal-finance-platform.git
cd finora-personal-finance-platform
```

### 2. Create and activate a virtual environment

```bash
python -m venv .venv
```

**Windows PowerShell:**

```powershell
.venv\Scripts\Activate.ps1
```

**macOS / Linux:**

```bash
source .venv/bin/activate
```

### 3. Install dependencies

```bash
python -m pip install -r backend/requirements.txt
```

### 4. Configure environment variables

Copy the example environment file:

**Windows PowerShell:**

```powershell
Copy-Item .env.example .env
```

**macOS / Linux:**

```bash
cp .env.example .env
```

Review the values in `.env`. In particular, replace the development JWT secret before using the application in any real or public deployment.

The default configuration uses SQLite and does not require an external AI provider. To enable an external AI provider for the AI Money Coach, configure the relevant provider, API key, base URL, and model values.

### 5. Run the application locally

From the project root:

```bash
python -m uvicorn backend.app.main:app --reload
```

Open the local URL shown in the terminal, normally:

```text
http://127.0.0.1:8000
```

### Docker Compose

Build and start the application:

```bash
docker compose up --build
```

Stop the application:

```bash
docker compose down
```

Docker Compose exposes the application on port `8000` and stores SQLite data in a persistent Docker volume.

## Testing

Run the backend test suite from the project root:

```bash
python -m pytest backend/tests -q
```

The test suite includes coverage for areas such as:

- Authentication and API integration
- Transactions and financial calculations
- Goals and health-score logic
- CSV and PDF import behavior
- OCR and upload validation
- Categorization and natural-language transaction parsing
- AI Coach behavior
- Rate limiting, CORS, and security hardening
- Upload-related frontend behavior

## Security and Privacy Notes

- Keep secrets in environment variables and do not commit `.env` files.
- Replace the development JWT secret before deployment.
- Review imported transaction rows before confirming them.
- Avoid uploading real financial documents to public demonstrations or shared environments.
- Use HTTPS and production-grade configuration before exposing the application publicly.
- Treat the included financial calculations, simulations, and suggestions as informational rather than guaranteed financial advice.

## Disclaimer

Finora is an educational and personal financial management application. Its calculations, simulations, and suggestions are intended for informational purposes only and should not be treated as personalized financial advice, investment recommendations, or guaranteed outcomes.

## License

This project is licensed under the [MIT License](LICENSE).

## Author

**Vaibhav Mittal**

- GitHub: [Vaibhav03050](https://github.com/Vaibhav03050)
- LinkedIn: [Vaibhav Mittal](https://www.linkedin.com/in/vaibhav-mittal-672621325/)
