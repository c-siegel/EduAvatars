"""
Security Functions for Authentication and Encryption

This module provides security-related functions for:
- Password hashing and verification
- JWT (JSON Web Token) creation and decoding
- API key encryption and decryption

What is this for?
These functions handle the core security operations needed for user authentication
and protecting sensitive data like API keys.

Security concepts:
- Hashing: One-way transformation of passwords (can't be reversed)
- JWT: Stateless authentication tokens that contain user information
- Encryption: Two-way transformation to protect sensitive data (can be decrypted)

How to use:
    from app.core.security import hash_password, verify_password, create_access_token
    
    # Hash a password (when user registers)
    hashed = hash_password("user_password")
    
    # Verify a password (when user logs in)
    is_valid = verify_password("user_password", hashed)
    
    # Create authentication token
    token = create_access_token(user_id="123", token_version=1)
"""

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from cryptography.fernet import Fernet

from app.core.config import settings


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.
    
    This function securely hashes a password before storing it in the database.
    Hashing is a one-way operation - you can't reverse it to get the original password.
    
    Why use bcrypt?
    - Automatically adds salt (random data) to prevent rainbow table attacks
    - Slow by design to prevent brute-force attacks
    - Widely used and battle-tested
    
    How it works:
    1. Takes the plain text password
    2. Generates a random salt
    3. Hashes the password with the salt
    4. Returns the hash (which includes the salt)
    """
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """
    Verify a password against its hash.
    
    This function checks if a plain text password matches a stored hash.
    It's used during login to authenticate users.
    
    How it works:
    1. Takes the plain text password and stored hash
    2. Extracts the salt from the hash
    3. Hashes the plain text password with the same salt
    4. Compares the new hash with the stored hash
    """
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(user_id: str, token_version: int, expires_delta: timedelta | None = None) -> str:
    """
    Create a JWT access token for authentication.
    
    What's in the token?
    - sub (subject): The user ID
    - tv (token version): Used to invalidate tokens (see User.token_version)
    - exp (expiration): When the token expires
    
    How it works:
    1. Creates a payload with user_id, token_version, and expiration time
    2. Signs the payload with the JWT secret key
    3. Returns the encoded token string
    """
    delta = expires_delta if expires_delta is not None else timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": user_id, "tv": token_version, "exp": datetime.now(timezone.utc) + delta}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> tuple[str, int]:
    """
    Decode and verify a JWT access token.
    
    How it works:
    1. Decodes the token using the JWT secret key
    2. Verifies the signature (ensures token wasn't tampered with)
    3. Checks that the token hasn't expired
    4. Returns the user_id and token_version
    
    Args:
        token: The JWT token string to decode
    
    Returns:
        tuple[str, int]: A tuple containing (user_id, token_version)
    
    Raises:
        jwt.ExpiredSignatureError: If token has expired
        jwt.InvalidTokenError: If token is invalid or tampered with
    
    Example:
        try:
            user_id, token_version = decode_access_token(token)
            # Use user_id to fetch user from database
            user = get_user(user_id)
        except jwt.ExpiredSignatureError:
            # Token expired, user needs to log in again
            return "Session expired"
    """
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    return payload["sub"], payload["tv"]


def _fernet() -> Fernet:
    """
    Create a Fernet encryption instance.
    
    What is Fernet?
    Fernet is a symmetric encryption algorithm that guarantees:
    - Messages cannot be read or altered without the key
    - Uses AES-128 in CBC mode with PKCS7 padding
    - Includes HMAC for authentication

    Note:
        This is a private function (starts with _) and should only be used
        internally by this module.
    """
    return Fernet(settings.api_key_encryption_secret.encode())


def encrypt_api_key(plaintext: str) -> str:
    """
    Encrypt an API key using Fernet symmetric encryption.
    
    How it works:
    1. Takes the plain text API key
    2. Encrypts it using Fernet (symmetric encryption)
    3. Returns the encrypted string (can be stored in database)
    
    Example:
        encrypted_key = encrypt_api_key("sk-1234567890abcdef")
        # Store 'encrypted_key' in database
        # Never store plain text API keys!
    """
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_api_key(ciphertext: str) -> str:
    """
    Decrypt an encrypted API key.
    
    How it works:
    1. Takes the encrypted API key from the database
    2. Decrypts it using Fernet
    3. Returns the original plain text API key
    
    Example:
        encrypted_key = get_encrypted_key_from_db(api_key_id)
        plain_key = decrypt_api_key(encrypted_key)
        # Use 'plain_key' to make API calls
        response = openai.ChatCompletion.create(api_key=plain_key, ...)
    """
    return _fernet().decrypt(ciphertext.encode()).decode()