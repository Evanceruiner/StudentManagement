# register.py
from database import db, send_email
from typing_auth import typing_auth
import re
import getpass

def validate_email(email):
    pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    return re.match(pattern, email) is not None

def validate_password(password):
    if len(password) < 8:
        return False
    if not re.search(r'[A-Z]', password):
        return False
    if not re.search(r'[a-z]', password):
        return False
    if not re.search(r'\d', password):
        return False
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False
    return True

def register():
    role = input("Role (admin/student): ").lower()
    if role not in ["admin", "student"]:
        print("Invalid role!")
        return
    if role == "admin":
        if getpass.getpass("Admin Passphrase: ") != "admin123":
            print("Wrong passphrase!")
            return
    email = input("Email: ")
    if not validate_email(email):
        print("Invalid email format!")
        return
    name = input("Name: ")
    password = getpass.getpass("Set password: ")
    if not validate_password(password):
        print("Password must be at least 8 characters long, with uppercase, lowercase, digit, and special character!")
        return
    user_id = db.generate_token(role)
    expected_phrase = input("Change phrase (optional, default 'thequickbrownfox'): ") or "thequickbrownfox"
    typing_data = typing_auth(user_id, "register", expected_phrase, samples_needed=5)
    
    expected_keystrokes_per_sample = len(expected_phrase)
    min_keystrokes = 5 * expected_keystrokes_per_sample
    if typing_data["samples"] < 5 or len(typing_data["keystrokes"]) < min_keystrokes:
        print(f"Typing failed! Need 5 valid samples with at least {min_keystrokes} keystrokes (got {typing_data['samples']} samples, {len(typing_data['keystrokes'])} keystrokes).")
        return
    
    for ks in typing_data["keystrokes"]:
        if "dwell_time" not in ks:
            print("Registration failed: Missing 'dwell_time' in keystroke data.")
            return
        if "flight_time" not in ks and ks != typing_data["keystrokes"][-1]:
            print("Registration failed: Missing 'flight_time' in keystroke data.")
            return
    
    token, secret = db.generate_totp_token(email)
    if send_email(email, "Registration Token", f"Your TOTP token (valid for 5 minutes): {token}"):
        user_token = input("Enter token: ")
        if db.verify_totp_token(user_token, secret):
            if db.add_user(user_id, email, password, role, name):
                db.save_typing_dynamics(user_id, typing_data["features"])
                db.save_keystrokes(user_id, typing_data["keystrokes"])
                print(f"Registration successful! Your ID: {user_id}")
            else:
                print("Registration failed: Email already exists!")
        else:
            print("Invalid or expired token!")
    else:
        print("Email sending failed!")