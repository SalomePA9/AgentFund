"""
Encryption utilities for secure storage of sensitive data.

Uses Fernet symmetric encryption with a server-side key.
"""

import base64
import logging
import os
import secrets

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)


class EncryptionService:
    """
    Service for encrypting and decrypting sensitive data.

    Uses Fernet symmetric encryption derived from a master key.
    """

    def __init__(self, master_key: str | None = None):
        """
        Initialize encryption service.

        Args:
            master_key: Master encryption key (from environment if not provided)
        """
        if master_key:
            self._key = master_key
        else:
            self._key = os.environ.get("ENCRYPTION_KEY")

        if not self._key:
            logger.warning(
                "No ENCRYPTION_KEY found. Generating temporary key. "
                "This key will change on restart - set ENCRYPTION_KEY env var for persistence!"
            )
            self._key = Fernet.generate_key().decode()

        self._fernet = self._create_fernet(self._key)

    def _create_fernet(self, key: str) -> Fernet:
        """Create Fernet instance from key string."""
        # If key is already a valid Fernet key (44 chars base64), use directly
        try:
            if len(key) == 44:
                return Fernet(key.encode())
        except Exception:
            pass

        # Otherwise derive a key from the string
        salt = b"agentfund_salt_v1"  # Fixed salt for consistent derivation
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        derived_key = base64.urlsafe_b64encode(kdf.derive(key.encode()))
        return Fernet(derived_key)

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt a string.

        Args:
            plaintext: String to encrypt

        Returns:
            Base64-encoded encrypted string
        """
        if not plaintext:
            return ""

        try:
            encrypted = self._fernet.encrypt(plaintext.encode())
            return encrypted.decode()
        except Exception as e:
            logger.error(f"Encryption error: {str(e)}")
            raise

    def decrypt(self, ciphertext: str) -> str:
        """
        Decrypt an encrypted string.

        Args:
            ciphertext: Base64-encoded encrypted string

        Returns:
            Decrypted plaintext string
        """
        if not ciphertext:
            return ""

        try:
            decrypted = self._fernet.decrypt(ciphertext.encode())
            return decrypted.decode()
        except InvalidToken:
            logger.error("Invalid encryption token - key may have changed")
            raise ValueError("Unable to decrypt - invalid key or corrupted data")
        except Exception as e:
            logger.error(f"Decryption error: {str(e)}")
            raise

    def encrypt_dict(self, data: dict, keys_to_encrypt: list[str]) -> dict:
        """
        Encrypt specific keys in a dictionary.

        Args:
            data: Dictionary with data
            keys_to_encrypt: List of keys to encrypt

        Returns:
            Dictionary with specified keys encrypted
        """
        result = data.copy()
        for key in keys_to_encrypt:
            if key in result and result[key]:
                result[key] = self.encrypt(str(result[key]))
        return result

    def decrypt_dict(self, data: dict, keys_to_decrypt: list[str]) -> dict:
        """
        Decrypt specific keys in a dictionary.

        Args:
            data: Dictionary with encrypted data
            keys_to_decrypt: List of keys to decrypt

        Returns:
            Dictionary with specified keys decrypted
        """
        result = data.copy()
        for key in keys_to_decrypt:
            if key in result and result[key]:
                result[key] = self.decrypt(str(result[key]))
        return result


# Global encryption service instance
_encryption_service: EncryptionService | None = None


def get_encryption_service() -> EncryptionService:
    """Get the global encryption service instance."""
    global _encryption_service
    if _encryption_service is None:
        _encryption_service = EncryptionService()
    return _encryption_service


def encrypt_api_key(api_key: str) -> str:
    """Encrypt an API key for storage."""
    return get_encryption_service().encrypt(api_key)


def decrypt_api_key(encrypted_key: str) -> str:
    """Decrypt an API key from storage."""
    return get_encryption_service().decrypt(encrypted_key)


def generate_encryption_key() -> str:
    """
    Generate a new Fernet encryption key.

    Use this to generate a key for ENCRYPTION_KEY environment variable.
    """
    return Fernet.generate_key().decode()
