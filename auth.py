"""
auth.py — password hashing + login/signup logic for BRIM.

Uses salted SHA-256 (via hashlib.pbkdf2_hmac) so the app has zero external
dependency beyond the standard library for auth. This is adequate for a
small-business tool; for a larger production deployment, consider swapping
in bcrypt/argon2 (e.g. via the `passlib` package).
"""

import hashlib
import os
import binascii

import db


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return binascii.hexlify(salt).decode() + "$" + binascii.hexlify(dk).decode()


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt_hex, dk_hex = stored_hash.split("$")
        salt = binascii.unhexlify(salt_hex)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
        return binascii.hexlify(dk).decode() == dk_hex
    except Exception:
        return False


def signup(username, email, password, business_name, business_type, phone):
    if db.get_user_by_username(username):
        return False, "That username is already taken."
    if db.get_user_by_email(email):
        return False, "An account with that email already exists."
    if len(password) < 6:
        return False, "Password must be at least 6 characters."
    pw_hash = hash_password(password)
    user_id = db.create_user(username, email, pw_hash, business_name, business_type, phone)
    return True, user_id


def login(username_or_email, password):
    user = db.get_user_by_username(username_or_email) or db.get_user_by_email(username_or_email)
    if not user:
        return False, "No account found with that username/email."
    if not verify_password(password, user["password_hash"]):
        return False, "Incorrect password."
    return True, user


def change_password(user_id, old_password, new_password):
    user = db.get_user_by_id(user_id)
    if not verify_password(old_password, user["password_hash"]):
        return False, "Current password is incorrect."
    if len(new_password) < 6:
        return False, "New password must be at least 6 characters."
    db.update_password(user_id, hash_password(new_password))
    return True, "Password updated."
