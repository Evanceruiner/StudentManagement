# login.py
from database import db, send_email
from typing_auth import typing_auth
import time
import os
import pickle
import numpy as np
import getpass
import re

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

def verify_typing_features(login_features, stored_features):
    dwell_threshold = 0.3
    flight_threshold = 0.3
    error_threshold = 0.2

    dwell_ok = abs(login_features["avgDwell"] - stored_features["avgDwell"]) <= stored_features["avgDwell"] * dwell_threshold
    flight_ok = abs(login_features["avgFlight"] - stored_features["avgFlight"]) <= stored_features["avgFlight"] * flight_threshold
    error_ok = abs(login_features["errorRate"] - stored_features["errorRate"]) <= error_threshold and 0 <= login_features["errorRate"] <= 1

    print(f"Typing Check - Dwell: {login_features['avgDwell']:.2f} vs {stored_features['avgDwell']:.2f} ({dwell_ok}), "
          f"Flight: {login_features['avgFlight']:.2f} vs {stored_features['avgFlight']:.2f} ({flight_ok}), "
          f"Error: {login_features['errorRate']:.2f} vs {stored_features['errorRate']:.2f} ({error_ok})")

    return dwell_ok and flight_ok and error_ok

def login():
    role = input("Role (admin/student): ").lower()
    if role not in ["admin", "student"]:
        print("Invalid role!")
        return None

    email = input("Email: ")
    if not validate_email(email):
        print("Invalid email format!")
        return None

    user_check = db.get_user_by_email(email)
    if not user_check:
        print("User does not exist!")
        return None

    if user_check["role"] != role:
        print("Role does not match!")
        return None

    user_id = input("User ID: ")
    user = db.get_user_by_id(user_id)
    if not user or user["email"] != email:
        print("Invalid user ID or email mismatch!")
        return None

    password = getpass.getpass("Password: ")
    if not validate_password(password):
        print("Password must be at least 8 characters long, with uppercase, lowercase, digit, and special character!")
        return None

    user = db.check_password(email, password)
    if not user:
        print("Invalid email or password!")
        attempts = db.get_user_by_email(email)["failed_attempts"]
        if attempts == 1:
            print("Warning: 3 failed attempts will lock your account for 30 seconds.")
        elif attempts == 2:
            print("One more failed attempt will lock your account for 30 seconds.")
        elif attempts == 3:
            print("Account locked for 30 seconds due to 3 failed attempts.")
        elif attempts > 3:
            print(f"{6 - attempts} attempts left before permanent lockout.")
        return None

    if user["lockout_count"] >= 2:
        print("Account permanently locked due to excessive failed attempts!")
        return None

    if user["lockout_time"] > time.time():
        remaining = int(user["lockout_time"] - time.time())
        print(f"Account locked! Please try again in {remaining} seconds.")
        return None

    typing_data = None

    if role == "student":
        stored_profile = db.get_user_typing_profile(user_id)
        if not stored_profile:
            print("No typing profile found! Login aborted.")
            return None

        typing_data = typing_auth(user_id, "authenticate", samples_needed=3)
        if typing_data["samples"] < 3 or len(typing_data["keystrokes"]) < 3:
            print("Typing failed! Need 3 valid samples.")
            if user_check:
                db.increment_failed_attempts(email)
                attempts = db.get_user_by_email(email)["failed_attempts"]
                if attempts == 1:
                    print("Warning: 3 failed attempts will lock your account for 30 seconds.")
                elif attempts == 2:
                    print("One more failed attempt will lock your account for 30 seconds.")
                elif attempts == 3:
                    print("Account locked for 30 seconds due to 3 failed attempts.")
                elif attempts > 3:
                    print(f"{6 - attempts} attempts left before permanent lockout.")
            return None

        if not verify_typing_features(typing_data["features"], stored_profile):
            print("Typing verification failed (threshold check)!")
            if user_check:
                db.increment_failed_attempts(email)
                attempts = db.get_user_by_email(email)["failed_attempts"]
                if attempts == 1:
                    print("Warning: 3 failed attempts will lock your account for 30 seconds.")
                elif attempts == 2:
                    print("One more failed attempt will lock your account for 30 seconds.")
                elif attempts == 3:
                    print("Account locked for 30 seconds due to 3 failed attempts.")
                elif attempts > 3:
                    print(f"{6 - attempts} attempts left before permanent lockout.")
            return None

        model_verified = True
        if os.path.exists("typing_model.pkl"):
            try:
                with open("typing_model.pkl", "rb") as f:
                    model = pickle.load(f)
                features = np.array([[typing_data["features"]["avgDwell"], 
                                     typing_data["features"]["avgFlight"], 
                                     typing_data["features"]["errorRate"]]])
                predicted_user = model.predict(features)[0]
                model_verified = predicted_user == user_id
                print(f"k-NN Prediction: {predicted_user} (Match: {model_verified})")
                if not model_verified:
                    print("Typing verification failed (k-NN check)!")
                    if user_check:
                        db.increment_failed_attempts(email)
                        attempts = db.get_user_by_email(email)["failed_attempts"]
                        if attempts == 1:
                            print("Warning: 3 failed attempts will lock your account for 30 seconds.")
                        elif attempts == 2:
                            print("One more failed attempt will lock your account for 30 seconds.")
                        elif attempts == 3:
                            print("Account locked for 30 seconds due to 3 failed attempts.")
                        elif attempts > 3:
                            print(f"{6 - attempts} attempts left before permanent lockout.")
                    return None
            except Exception as e:
                print(f"k-NN model check failed: {str(e)}. Proceeding with threshold check only.")

    token, secret = db.generate_totp_token(email)
    if send_email(email, "Login Token", f"Your TOTP token (valid for 5 minutes): {token}"):
        user_token = input("Enter token: ")
        if db.verify_totp_token(user_token, secret):
            print("Login successful!")
            if role == "student" and typing_data:
                db.save_keystrokes(user_id, typing_data["keystrokes"])
                db.update_typing_profile(user_id, typing_data["features"], new_samples=3)
            return user
        else:
            print("Invalid or expired token!")
            if user_check:
                db.increment_failed_attempts(email)
                attempts = db.get_user_by_email(email)["failed_attempts"]
                if attempts == 1:
                    print("Warning: 3 failed attempts will lock your account for 30 seconds.")
                elif attempts == 2:
                    print("One more failed attempt will lock your account for 30 seconds.")
                elif attempts == 3:
                    print("Account locked for 30 seconds due to 3 failed attempts.")
                elif attempts > 3:
                    print(f"{6 - attempts} attempts left before permanent lockout.")
            return None
    else:
        print("Email sending failed!")
        return None