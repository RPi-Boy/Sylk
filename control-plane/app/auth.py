import csv
import os
import hashlib
from typing import Optional
from pydantic import BaseModel

USERS_FILE = os.path.join(os.path.dirname(__file__), "..", "users.csv")

class UserCreate(BaseModel):
    username: str
    email: str
    password: str

class UserLogin(BaseModel):
    email: str
    password: str

def get_password_hash(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return get_password_hash(plain_password) == hashed_password

def initialize_csv():
    """Ensure the CSV file exists with headers."""
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["username", "email", "password_hash"])

def get_user_by_email(email: str) -> Optional[dict]:
    """Retrieve a user record by email."""
    initialize_csv()
    with open(USERS_FILE, mode='r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            if row["email"] == email:
                return row
    return None

def create_user(user: UserCreate) -> bool:
    """Create a new user. Returns False if email already exists."""
    initialize_csv()
    if get_user_by_email(user.email):
        return False # User already exists
    
    with open(USERS_FILE, mode='a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([user.username, user.email, get_password_hash(user.password)])
    return True
