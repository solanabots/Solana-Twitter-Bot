import requests
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import os
import json
from typing import Dict, Any

class PredatorSDK:
    def __init__(self, config: Dict[str, str] = {}):
        self.base_url = config.get('base_url', 'https://api.predator.bot')
        self.encryption_key = None
        self.session = requests.Session()
        self.session.headers.update({'Content-Type': 'application/json'})

    async def initialize(self):
        if not self.encryption_key:
            try:
                response = self.session.get(f"{self.base_url}/encryption-key")
                response.raise_for_status()
                self.encryption_key = bytes.fromhex(response.json()['encryptionKey'])
            except requests.RequestException as e:
                raise Exception('An error occurred.') from e

    async def buy(self, options: Dict[str, str]) -> Dict[str, Any]:
        return await self._execute_operation('buy', options)

    async def sell(self, options: Dict[str, str]) -> Dict[str, Any]:
        percentage = float(options['percentage'])
        if not 0 < percentage <= 100:
            raise ValueError('Invalid percentage. Must be a number between 0 and 100.')
        
        sell_options = options.copy()
        sell_options['amount'] = percentage
        return await self._execute_operation('sell', sell_options)

    async def create(self, options: Dict[str, str]) -> Dict[str, Any]:
        return await self._execute_operation('create', options)

    async def _execute_operation(self, operation: str, options: Dict[str, str]) -> Dict[str, Any]:
        await self.initialize()
        
        endpoint = f"/{operation}"
        data = self._prepare_data(operation, options)
        
        try:
            encrypted_data = self._encrypt(json.dumps(data))
            response = self.session.post(f"{self.base_url}{endpoint}", json={'encryptedData': encrypted_data})
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise self._handle_error(e)

    def _prepare_data(self, operation: str, options: Dict[str, str]) -> Dict[str, Any]:
        base_data = {
            'privateKeys': options['privateKeys']
        }

        if operation in ['buy', 'sell']:
            return {
                **base_data,
                'tokenBAddress': options['tokenAddress'],
                'tokenBAmount': options['amount']
            }
        elif operation == 'create':
            return {
                **base_data,
                'tokenBAddress': options['devPrivateKey'],
                'tokenBAmount': options['amount'],
                'tokenName': options['name'],
                'tokenSymbol': options['symbol'],
                'tokenDescription': options['description'],
                'telegramLink': options['telegram'],
                'twitterLink': options['twitter'],
                'websiteLink': options['website'],
                'fileUrl': options['file']
            }
        else:
            raise ValueError(f"Unsupported operation: {operation}")

    def _encrypt(self, text: str) -> str:
        if not self.encryption_key:
            raise Exception('Encryption key not initialized. Call initialize() first.')
        iv = os.urandom(16)
        cipher = Cipher(algorithms.AES(self.encryption_key), modes.CBC(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        padded_text = self._pad(text.encode())
        encrypted = encryptor.update(padded_text) + encryptor.finalize()
        return f"{iv.hex()}:{encrypted.hex()}"

    @staticmethod
    def _pad(s: bytes) -> bytes:
        return s + (16 - len(s) % 16) * chr(16 - len(s) % 16).encode()

    @staticmethod
    def _handle_error(error: requests.RequestException) -> Exception:
        if error.response is not None:
            return Exception(f"API error: {error.response.status_code} - {error.response.text}")
        elif error.request is not None:
            return Exception('No response received from the server')
        else:
            return Exception(f"Request error: {str(error)}")