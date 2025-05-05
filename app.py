# app.py
from register import register
from login import login
from admin_dashboard import admin_dashboard
from student_dashboard import student_dashboard
from database import db

def main_menu():
    while True:
        print("\n=== SmartSecure System ===")
        print("\n=== A Trusted Student Plartform with improved Security and Advanced Authentication Module ====")
        print("1. Sign Up")
        print("2. Sign In")
        print("3. Exit")
        choice = input("Select an option (1-3): ")

        if choice == "1":
            register()
        elif choice == "2":
            user = login()
            if user:
                if user["role"] == "admin":
                    admin_dashboard(user)
                elif user["role"] == "student":
                    student_dashboard(user)
                else:
                    print("Unknown role! Logging out.")
        elif choice == "3":
            print("Exiting...")
            break
        else:
            print("Invalid option! Please select 1, 2, or 3.")

if __name__ == "__main__":
    try:
        main_menu()
    finally:
        db.close()