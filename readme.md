# Stock Tracker App
A simple Django app to track stocks and generate buy/sell signals.

What it Does
Upload CSV files with stock data

Automatically shows BUY when price drops 3% or more

Automatically shows SELL 5 days after BUY

Shows HOLD for all other days

View all stocks on dashboard

Generate reports

Quick Start
Install

bash
python3 -m venv env
source env/bin/activate
pip install -r requirements.txt
python manage.py migrate
Run

bash
python manage.py runserver
Use

Go to http://localhost:8000/

Click "Upload Data"

Upload CSV file with columns: ticker,date,close

View results on dashboard

File Format
Create a CSV file like this:

csv
ticker,date,close
TEST-1,2024-01-01,100.00
TEST-1,2024-01-02,103.00
TEST-1,2024-01-03,99.91
How It Works
BUY: When price drops 3% from yesterday
SELL: 5 days after a BUY
HOLD: All other days

Project Structure
text
stock_tracker/
├── stocks/           # Main app
├── templates/        # HTML pages
├── manage.py         # Run commands
└── requirements.txt  # Python packages
Commands
bash
# Start server
python manage.py runserver

# Create admin user
python manage.py createsuperuser

# Update database
python manage.py migrate