# student_dashboard.py
from database import db
from typing_auth import typing_auth
import json
import time
import numpy as np
import pickle
import os

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

def typing_verification(user_id):
    stored_profile = db.get_user_typing_profile(user_id)
    if not stored_profile:
        print("No typing profile found! Verification aborted.")
        return False

    typing_data = typing_auth(user_id, "verify", samples_needed=3)
    if typing_data["samples"] < 3 or len(typing_data["keystrokes"]) < 3:
        print("Typing failed! Need 3 valid samples.")
        return False

    if not verify_typing_features(typing_data["features"], stored_profile):
        print("Typing verification failed (threshold check)!")
        return False

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
                return False
        except Exception as e:
            print(f"k-NN model check failed: {str(e)}. Proceeding with threshold check only.")

    return True

def view_assigned_test_ids(user_id):
    test_ids = db.get_assigned_test_ids(user_id)
    if not test_ids:
        print("No tests assigned to you.")
    else:
        print("\n=== Assigned Test IDs ===")
        for i, test_id in enumerate(test_ids, 1):
            print(f"{i}. {test_id}")

def take_test(user):
    user_id = user["user_id"]
    test_id = input("Enter Test ID: ")
    test = db.get_test(test_id)
    if not test:
        print("Invalid Test ID!")
        return

    if not db.is_test_assigned(test_id, user_id):
        print("This test is not assigned to you!")
        return

    print("Verifying identity with typing test...")
    if not typing_verification(user_id):
        print("Identity verification failed! Cannot proceed with the test.")
        return

    typing_data = typing_auth(user_id, "test", samples_needed=3)
    stored_profile = db.get_user_typing_profile(user_id)
    if not stored_profile or typing_data["samples"] < 3 or len(typing_data["keystrokes"]) < 3:
        print("Typing test failed! Need 3 valid samples for confidence calculation.")
        return

    stored_confidence = 1.0 - stored_profile["errorRate"]
    test_confidence = 1.0 - typing_data["features"]["errorRate"]

    print("\n=== Taking Test ===")
    questions = test["questions"]
    answers = {}
    start_time = time.time()

    for qid, question in questions.items():
        print(f"\nQuestion {qid}: {question['text']}")
        for i, option in enumerate(question["options"], 1):
            print(f"{i}. {option}")
        while True:
            try:
                choice = int(input("Select option (1-4): "))
                if 1 <= choice <= 4:
                    answers[qid] = choice - 1
                    break
                else:
                    print("Please select a number between 1 and 4.")
            except ValueError:
                print("Invalid input! Please enter a number.")

    end_time = time.time()
    duration = end_time - start_time
    print(f"\nTest completed in {duration:.2f} seconds.")

    if db.save_test_submission(user_id, test_id, answers, stored_confidence, test_confidence):
        print("Test submitted successfully!")
    else:
        print("Failed to submit test!")

def student_dashboard(user):
    while True:
        print("\n=== Student Dashboard ===")
        print("1. View Details")
        print("2. View Assigned Test IDs")
        print("3. Take Test")
        print("4. Logout")
        choice = input("Select an option (1-4): ")

        if choice == "1":
            print("\n=== Your Details ===")
            print(f"User ID: {user['user_id']}")
            print(f"Name: {user['name']}")
            print(f"Email: {user['email']}")
            print(f"Role: {user['role']}")
            profile = db.get_user_typing_profile(user["user_id"])
            if profile:
                print("\nTyping Profile:")
                print(f"Average Dwell Time: {profile['avgDwell']:.2f} ms")
                print(f"Average Flight Time: {profile['avgFlight']:.2f} ms")
                print(f"Error Rate: {profile['errorRate']:.2f}")
            else:
                print("No typing profile available.")

        elif choice == "2":
            view_assigned_test_ids(user["user_id"])

        elif choice == "3":
            take_test(user)

        elif choice == "4":
            print("Logging out...")
            break

        else:
            print("Invalid option! Please select 1, 2, 3, or 4.")