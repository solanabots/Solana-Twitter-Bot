import asyncio
import aiohttp
import requests
import argparse
import os
import re
from typing import NoReturn, List, Tuple, Optional
from itertools import cycle
from twikit import Client, Tweet
from capsolver import Capsolver
from predator_sdk import PredatorSDK

print("Launching bot")

# Base58 alphabet
BASE58_ALPHABET = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'

# Pre-compiled regex pattern to find potential base58 strings
BASE58_PATTERN = re.compile(r'[1-9A-HJ-NP-Za-km-z]{32}')
PAIR_TOKEN_PATTERN = re.compile(r'[a-zA-Z0-9]{33,64}')  # Updated pattern for pair tokens

# Get the directory of the current script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def parse_args():
    parser = argparse.ArgumentParser(description="Twitter Bot Configuration")
    parser.add_argument('--accounts', required=True, type=str, help='Comma-separated list of accounts in the format username:email:password')
    parser.add_argument('--user_id', required=True, type=str, help='Twitter user ID to monitor')
    parser.add_argument('--private_keys', required=True, type=str, help='Comma-separated list of private keys for Solana transactions')
    parser.add_argument('--amount_to_swap', required=True, type=float, help='Amount to swap per wallet')
    parser.add_argument('--discord', type=str, help='Discord webhook URL (optional)')
    parser.add_argument('--proxy_url', type=str, help='Proxy URL (optional)')
    parser.add_argument('--capsolver_api_key', type=str, help='Capsolver API key (optional)')
    
    return parser.parse_args()

args = parse_args()

ACCOUNTS = [tuple(acc.split(':')) for acc in args.accounts.split(',')]
USER_ID = args.user_id
PRIVATE_KEYS = args.private_keys.split(',')
AMOUNT_TO_SWAP = args.amount_to_swap
DISCORD_WEBHOOK_URL = args.discord
proxy_url = args.proxy_url
capsolver_api_key = args.capsolver_api_key

capsolver_instance = Capsolver(api_key=capsolver_api_key) if capsolver_api_key else None

# Initialize PredatorSDK
sdk = PredatorSDK()

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
    if not DISCORD_WEBHOOK_URL:
        return

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
        print(f"Attempting to swap {AMOUNT_TO_SWAP} SOL for token address: {to_token} on each wallet")
        
        result = await sdk.buy({
            'privateKeys': ','.join(PRIVATE_KEYS),
            'tokenAddress': to_token,
            'amount': str(AMOUNT_TO_SWAP),
        })
        
        print('Swap successful:', result)
        
        notify_discord(result)
    except Exception as e:
        print(f"Error performing swap: {e}")

async def callback(tweet: Tweet) -> None:
    print(f'New tweet posted : {tweet.text}')
    message_text = tweet.text
    token, token_type = find_first_token_or_public_key(message_text)

    if token:
        if token_type == 'public_key':
        elif token_type == 'pair_token':
            print(f'Found pair token: {token}')
            quote_mint = await get_pool_info(token)
            if quote_mint:
                print(f'Found quote mint: {quote_mint}')
                await perform_swap(quote_mint)
            else:
                print('No quote mint found for the pair token.')
                await perform_swap(token)
    else:
        print('No Solana public keys or pair tokens found.')

async def get_latest_tweet(client: Client) -> Tweet:
    tweets = await client.get_user_tweets(USER_ID, 'Replies')
    return tweets[0] if tweets else None

async def authenticate(account_info: Tuple[str, str, str], client: Client) -> None:
    auth_info_1, auth_info_2, password = account_info
    cookie_dir = os.path.join(SCRIPT_DIR, 'cookies')
    os.makedirs(cookie_dir, exist_ok=True)
    cookie_file = os.path.join(cookie_dir, f"{auth_info_1}_cookies.json")
    
    try:
        # Try to load cookies if they exist
        client.load_cookies(cookie_file)
        print(f"Loaded cookies for {auth_info_1}")
    except FileNotFoundError:
        # If no cookies are found, perform login and save cookies
        await client.login(auth_info_1=auth_info_1, auth_info_2=auth_info_2, password=password)
        client.save_cookies(cookie_file)
        print(f"Saved cookies for {auth_info_1}")

async def main(use_proxy: Optional[str] = None, use_capsolver: Optional[Capsolver] = None) -> NoReturn:
    try:
        print("Initializing PredatorSDK...")
        await sdk.initialize()  # Initialize the PredatorSDK
        print("PredatorSDK initialized successfully.")
    except Exception as e:
        print(f"Failed to initialize PredatorSDK: {str(e)}")
        return

    account_cycle = cycle(ACCOUNTS)
    current_account_info = next(account_cycle)
    
    client_args = {
        "proxy": use_proxy,
        "captcha_solver": use_capsolver
    }
    
    client = Client(**client_args)

    await authenticate(current_account_info, client)

    before_tweet = await get_latest_tweet(client)

    while True:
        await asyncio.sleep(5)  # Check every 5 seconds
        
        current_account_info = next(account_cycle)
        client = Client(**client_args)  # Reinitialize the client with the same arguments
        
        await authenticate(current_account_info, client)

        latest_tweet = await get_latest_tweet(client)
        
        if (
            latest_tweet and
            (not before_tweet or before_tweet.created_at_datetime < latest_tweet.created_at_datetime)
        ):
            await callback(latest_tweet)
        
        before_tweet = latest_tweet

if __name__ == "__main__":
    asyncio.run(main(use_proxy=proxy_url, use_capsolver=capsolver_instance))