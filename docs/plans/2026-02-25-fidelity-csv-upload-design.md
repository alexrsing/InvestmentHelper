# Fidelity CSV Upload Design

## Overview

Upload Fidelity portfolio statement CSVs via the frontend. Backend parses the CSV, replaces the user's portfolio holdings in DynamoDB, and returns structured JSON.

## CSV Format

Fidelity statements have two sections:
1. Account summary (lines 1-3) — skipped
2. Holdings detail (after `Symbol/CUSIP` header row) — parsed

Holdings rows contain: Symbol, Description, Quantity, Price, Beginning Value, Ending Value, Cost Basis. Rows to skip: blank lines, account number headers, asset class headers (e.g. "Stocks"), subtotal rows.

## Backend

### csv_service (`backend/app/services/csv_service.py`)

Parses Fidelity CSV format:
- Finds the holdings header row (`Symbol/CUSIP,Description,Quantity,Price,...`)
- Parses each data row, skipping non-data rows
- Extracts per holding: `ticker`, `quantity`, `cost_basis`
- Calculates `initial_value` (sum of cost basis)
- Calculates `total_value` (sum of ending values)
- Returns structured result

### Upload endpoint (`POST /api/v1/portfolio/upload`)

Added to existing portfolio router:
- Accepts multipart file upload
- Calls csv_service to parse
- Full replace of user's portfolio in DynamoDB (holdings + initial_value)
- Returns JSON: `total_value`, `initial_value`, `positions` (each: `ticker`, `quantity`, `cost_basis`)
- Requires Clerk JWT auth
- Validates CSV format

## Frontend

### Upload button on Dashboard

- Upload button in the Navbar or portfolio summary area
- File picker accepts `.csv` only
- Sends file to `POST /api/v1/portfolio/upload` with Clerk token
- On success, refreshes portfolio data
- Shows error message on failure
