import yfinance as yf
import json

# Test with a common ETF
ticker = "SPY"
print(f"Testing ticker: {ticker}\n")

# Get info
info = yf.Ticker(ticker).info

# Print all keys that contain 'price' or 'Price'
print("=== Keys containing 'price' or 'Price' ===")
price_keys = {k: v for k, v in info.items() if 'price' in k.lower()}
for key, value in sorted(price_keys.items()):
    print(f"{key}: {value}")

print("\n=== Keys containing 'market' or 'Market' ===")
market_keys = {k: v for k, v in info.items() if 'market' in k.lower()}
for key, value in sorted(market_keys.items()):
    print(f"{key}: {value}")

print("\n=== Keys containing 'change' or 'Change' ===")
change_keys = {k: v for k, v in info.items() if 'change' in k.lower()}
for key, value in sorted(change_keys.items()):
    print(f"{key}: {value}")

print("\n=== Volume keys ===")
volume_keys = {k: v for k, v in info.items() if 'volume' in k.lower()}
for key, value in sorted(volume_keys.items()):
    print(f"{key}: {value}")

print("\n=== All available keys ===")
print(sorted(info.keys()))
