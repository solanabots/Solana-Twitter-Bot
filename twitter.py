import time
import json
import re
import os
import asyncio
import aiohttp
import requests
import argparse
from typing import NoReturn, List, Tuple, Optional
from itertools import cycle
from twikit import Client, Tweet
from capsolver import Capsolver
from solders.keypair import Keypair
from solanatracker import SolanaTracker

print("Launching bot")

# Base58 alphabet
BASE58_ALPHABET = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'

# Pre-compiled regex pattern to find potential base58 strings
BASE58_PATTERN = re.compile(r'[1-9A-HJ-NP-Za-km-z]{32,44}')
PAIR_TOKEN_PATTERN = re.compile(r'[a-z0-9]{44}')  # Adjust the pattern if needed

def parse_args():
    parser = argparse.ArgumentParser(description="Twitter Bot Configuration")
    parser.add_argument('--accounts', required=True, type=str, help='Comma-separated list of accounts in the format username:email:password')
    parser.add_argument('--user_id', required=True, type=str, help='Twitter user ID to monitor')
    parser.add_argument('--rate_limit_requests', required=True, type=int, help='Number of requests per interval')
    parser.add_argument('--rate_limit_interval', required=True, type=int, help='Rate limit interval in seconds')
    parser.add_argument('--private_key', required=True, type=str, help='Private key for Solana transactions')
    parser.add_argument('--amount_to_swap', required=True, type=float, help='Amount to swap')
    parser.add_argument('--slippage', required=True, type=float, help='Slippage percentage')
    parser.add_argument('--priority_fee', required=True, type=float, help='Priority fee for transactions')
    parser.add_argument('--discord', required=True, type=str, help='Discord webhook URL')
    parser.add_argument('--proxy_url', type=str, default=None, help='Proxy URL (optional)')
    parser.add_argument('--capsolver_api_key', type=str, default=None, help='Capsolver API key (optional)')
    
    return parser.parse_args()

args = parse_args()

ACCOUNTS = [tuple(acc.split(':')) for acc in args.accounts.split(',')]
USER_ID = args.user_id
RATE_LIMIT_REQUESTS = args.rate_limit_requests
RATE_LIMIT_INTERVAL = args.rate_limit_interval  # in seconds
PRIVATE_KEY = args.private_key
AMOUNT_TO_SWAP = args.amount_to_swap
SLIPPAGE = args.slippage
PRIORITY_FEE = args.priority_fee
DISCORD_WEBHOOK_URL = args.discord
proxy_url = args.proxy_url
capsolver_api_key = args.capsolver_api_key

capsolver_instance = Capsolver(api_key=capsolver_api_key) if capsolver_api_key else None

def is_base58(s: str) -> bool:
    return all(c in BASE58_ALPHABET for c in s)

def resolve_redirect(url: str) -> str:
    try:
        response = requests.head(url, allow_redirects=True)
        return response.url
    except requests.RequestException as e:
        print(f"Error resolving {url}: {e}")
        return url

def find_first_token_or_public_key(text: str):
    potential_keys = BASE58_PATTERN.findall(text)
    potential_pair_tokens = PAIR_TOKEN_PATTERN.findall(text)

    for token in potential_pair_tokens:
        return token, 'pair_token'
    
    for key in potential_keys:
        if is_base58(key):
            return key, 'public_key'

    # Check for t.co links and resolve them
    tco_links = re.findall(r'https://t\.co/\S+', text)
    for tco_link in tco_links:
        resolved_url = resolve_redirect(tco_link)
        potential_keys = BASE58_PATTERN.findall(resolved_url)
        potential_pair_tokens = PAIR_TOKEN_PATTERN.findall(resolved_url)

        for token in potential_pair_tokens:
            return token, 'pair_token'
        
        for key in potential_keys:
            if is_base58(key):
                return key, 'public_key'

    return None, None

def notify_discord(txid: str):
    message = {
        "content": f"Swap successful!\nTransaction ID: {txid}\nTransaction URL: https://solscan.io/tx/{txid}"
    }
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=message)
        if response.status_code == 204:
            print("Discord notification sent successfully.")
        else:
            print(f"Failed to send Discord notification. Status code: {response.status_code}")
    except Exception as e:
        print(f"Error sending Discord notification: {e}")

async def get_pool_info(pair_token: str):
    url = f"https://api.dexscreener.com/latest/dex/pairs/solana/{pair_token}"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()
                pairs = data.get("pairs", [])
                if pairs:
                    for token in pairs:
                        contract_id = token["baseToken"]["address"]
                        return contract_id
    return None

async def perform_swap(to_token: str):
    try:
        keypair = Keypair.from_base58_string(PRIVATE_KEY)

        solana_tracker = SolanaTracker(keypair, "https://api.solanatracker.io/rpc")

        swap_response = await solana_tracker.get_swap_instructions(
            "So11111111111111111111111111111111111111112",  # From Token (SOL)
            to_token,  # To Token (found in tweet)
            AMOUNT_TO_SWAP,  # Amount to swap from config
            SLIPPAGE,  # Slippage from config
            str(keypair.pubkey()),  # Payer public key
            PRIORITY_FEE,  # Priority fee from config (Recommended while network is congested)
            True,  # Force legacy transaction for Jupiter
        )

        txid = await solana_tracker.perform_swap(swap_response)

        print("Transaction ID:", txid)
        print("Transaction URL:", f"https://solscan.io/tx/{txid}")

        # Check if the Discord webhook URL is set before notifying
        if DISCORD_WEBHOOK_URL:
            notify_discord(txid)
        
    except Exception as e:
        print(f"Error performing swap: {e}")

async def callback(tweet: Tweet) -> None:
    print(f'New tweet posted : {tweet.text}')
    message_text = tweet.text
    token, token_type = find_first_token_or_public_key(message_text)

    if token:
        if token_type == 'public_key':
            print(f'Found Solana public key: {token}')
            await perform_swap(token)
        elif token_type == 'pair_token':
            print(f'Found pair token: {token}')
            quote_mint = await get_pool_info(token)
            if quote_mint:
                print(f'Found quote mint: {quote_mint}')
                await perform_swap(quote_mint)
            else:
                print('No quote mint found for the pair token.')
    else:
        print('No Solana public keys or pair tokens found.')

def get_latest_tweet(client: Client) -> Tweet:
    return client.get_user_tweets(USER_ID, 'Replies')[0]

def authenticate(account_info: Tuple[str, str, str], client: Client) -> None:
    auth_info_1, auth_info_2, password = account_info
    appdata_dir = os.getenv('APPDATA')
    cookie_dir = os.path.join(appdata_dir, 'predator', 'tools', 'Twitter')
    os.makedirs(cookie_dir, exist_ok=True)
    cookie_file = os.path.join(cookie_dir, f"{auth_info_1}_cookies.json")
    
    try:
        # Try to load cookies if they exist
        client.load_cookies(cookie_file)
        print(f"Loaded cookies for {auth_info_1}")
    except FileNotFoundError:
        # If no cookies are found, perform login and save cookies
        client.login(auth_info_1=auth_info_1, auth_info_2=auth_info_2, password=password)
        client.save_cookies(cookie_file)
        print(f"Saved cookies for {auth_info_1}")

def calculate_delay(num_accounts: int) -> float:
    total_requests = num_accounts * RATE_LIMIT_REQUESTS
    delay_between_requests = RATE_LIMIT_INTERVAL / total_requests
    return delay_between_requests

async def main(use_proxy: Optional[str] = None, use_capsolver: Optional[Capsolver] = None) -> NoReturn:
    num_accounts = len(ACCOUNTS)
    delay_between_requests = calculate_delay(num_accounts)
    
    account_cycle = cycle(ACCOUNTS)
    current_account_info = next(account_cycle)
    
    client_args = {
        "proxy": use_proxy,
        "captcha_solver": use_capsolver
    }
    
    client = Client(**client_args)

    authenticate(current_account_info, client)

    before_tweet = get_latest_tweet(client)

    while True:
        await asyncio.sleep(delay_between_requests)
        
        current_account_info = next(account_cycle)
        client = Client(**client_args)  # Reinitialize the client with the same arguments
        
        authenticate(current_account_info, client)

        latest_tweet = get_latest_tweet(client)
        
        if (
            before_tweet != latest_tweet and
            before_tweet.created_at_datetime < latest_tweet.created_at_datetime
        ):
            await callback(latest_tweet)
        
        before_tweet = latest_tweet

if __name__ == "__main__":
    asyncio.run(main(use_proxy=proxy_url, use_capsolver=capsolver_instance))
