# admin_dashboard.py
from database import db
import random
import string
import pickle
import os
import numpy as np
from sklearn.neighbors import KNeighborsClassifier

def generate_test_id():
    return "TE" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))

def create_test():
    num_questions = int(input("Number of questions: "))
    questions = {}
    for i in range(1, num_questions + 1):
        print(f"Question {i}:")
        text = input(f"Question {i}: ")
        options = [input(f"Option {j}: ") for j in range(1, 5)]
        correct = int(input("Correct answer (1-4): ")) - 1
        questions[str(i)] = {"text": text, "options": options, "correct": correct}
    assigned_ids = input("Student IDs (comma-separated): ").split(",")
    assigned_ids = [id.strip() for id in assigned_ids]
    test_id = generate_test_id()
    if db.create_test(test_id, questions, assigned_ids):
        print(f"Test created successfully! Test ID: {test_id}")
    else:
        print("Failed to create test!")

def train_knn_model():
    with db.conn.cursor() as cur:
        cur.execute("SELECT user_id, avg_dwell, avg_flight, error_rate FROM typing_profiles")
        profiles = cur.fetchall()
    
    if len(profiles) < 2:
        print("Not enough users to train the model (need at least 2).")
        return
    
    X = np.array([[p["avg_dwell"], p["avg_flight"], p["error_rate"]] for p in profiles])
    y = np.array([p["user_id"] for p in profiles])
    
    knn = KNeighborsClassifier(n_neighbors=min(3, len(profiles)))
    knn.fit(X, y)
    
    with open("typing_model.pkl", "wb") as f:
        pickle.dump(knn, f)
    print("k-NN model trained and saved!")

def admin_dashboard(user):
    while True:
        print("\n=== Admin Dashboard ===")
        print("1. Create Test")
        print("2. Train k-NN Model")
        print("3. Logout")
        choice = input("Select an option (1-3): ")

        if choice == "1":
            create_test()
        elif choice == "2":
            train_knn_model()
        elif choice == "3":
            print("Logging out...")
            break
        else:
            print("Invalid option! Please select 1, 2, or 3.")