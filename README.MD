# Twitter Solana Token Sniper Bot

This bot monitors a specific Twitter account for new tweets containing Solana token addresses or pair tokens. When a new token is detected, the bot automatically attempts to swap a specified amount of SOL for the new token using multiple wallets.

## Features

- Monitor a specific Twitter account for new tweets
- Detect Solana token addresses and pair tokens in tweets
- Automatically swap SOL for new tokens using the Predator SDK
- Support for multiple private keys (wallets)
- Optional Discord webhook notifications
- GUI for easy configuration and launching

## Prerequisites

- Python 3.7 or higher
- Solana wallet(s) with SOL balance
- Twitter account(s) for monitoring

## Installation

1. Clone this repository or download the source code.
2. Install the required packages:

```
pip install -r requirements.txt
```

3. Set up your configuration in the GUI or prepare a JSON configuration file.

## Usage

1. Run the GUI:

```
python gui.py
```

2. Fill in the required fields:
   - Private Keys (comma-separated): Your Solana wallet private keys
   - Accounts (username:email:password): Twitter account(s) for monitoring
   - User ID to Monitor: The Twitter user ID to watch for new tweets
   - Amount to Swap (per wallet): The amount of SOL to swap for each detected token (per wallet)
   - Discord Webhook (optional): URL for Discord notifications
   - Proxy URL (optional): If you need to use a proxy
   - Capsolver API Key (optional): For solving CAPTCHAs

3. Click "Run Bot" to start the bot, or use "Save Config" to save your configuration for later use.

Alternatively, you can run the bot directly from the command line:

```
python twitter.py --private_keys key1,key2,key3 --accounts user1:email1:pass1,user2:email2:pass2 --user_id TARGET_USER_ID --amount_to_swap 0.1 [--discord WEBHOOK_URL] [--proxy_url PROXY_URL] [--capsolver_api_key API_KEY]
```

## Disclaimer

This bot is for educational purposes only. Use it at your own risk. Be aware of the risks associated with cryptocurrency trading and always do your own research before investing.

## License

This project is licensed under the MIT License.
