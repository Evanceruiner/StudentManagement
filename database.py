# database.py
import os
import psycopg2
from psycopg2.extras import RealDictCursor
import random
import string
import bcrypt
import time
import pyotp
import json

class Database:
    def __init__(self):
        self.conn = psycopg2.connect(
            host=os.getenv("DB_HOST", "localhost"),
            dbname=os.getenv("DB_NAME", "SmartSecure"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", "CruseQ67"),
            cursor_factory=RealDictCursor
        )
        self.init_db()

    def init_db(self):
        with self.conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id VARCHAR(7) PRIMARY KEY,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    password VARCHAR(255) NOT NULL,
                    role VARCHAR(10) NOT NULL CHECK (role IN ('admin', 'student')),
                    name VARCHAR(255) NOT NULL,
                    failed_attempts INTEGER DEFAULT 0,
                    lockout_time REAL DEFAULT 0,
                    lockout_count INTEGER DEFAULT 0
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS typing_profiles (
                    user_id VARCHAR(7) PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
                    avg_dwell REAL NOT NULL,
                    avg_flight REAL NOT NULL,
                    error_rate REAL NOT NULL,
                    sample_count INTEGER DEFAULT 5
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS keystrokes (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(7) REFERENCES users(user_id) ON DELETE CASCADE,
                    key CHAR(1),
                    press_time REAL,
                    release_time REAL,
                    dwell_time REAL,
                    flight_time REAL
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS tests (
                    test_id VARCHAR(8) PRIMARY KEY,
                    questions JSONB NOT NULL,
                    assigned_ids JSONB NOT NULL,
                    replies JSONB DEFAULT '{}'
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS student_submissions (
                    user_id VARCHAR(7) REFERENCES users(user_id) ON DELETE CASCADE,
                    test_id VARCHAR(8),
                    taken_time TIMESTAMP NOT NULL,
                    stored_confidence REAL NOT NULL,
                    test_confidence REAL NOT NULL,
                    answers JSONB NOT NULL,
                    PRIMARY KEY (user_id, test_id)
                );
            """)
            self.conn.commit()

    def generate_token(self, role):
        prefix = "A" if role == "admin" else "S"
        return prefix + "".join(random.choices(string.digits, k=6))

    def add_user(self, user_id, email, password, role, name):
        hashed_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO users (user_id, email, password, role, name)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING user_id;
                """, (user_id, email, hashed_password, role, name))
                result = cur.fetchone()
                self.conn.commit()
                return result is not None
        except psycopg2.IntegrityError:
            self.conn.rollback()
            return False

    def get_user_by_email(self, email):
        with self.conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE email = %s", (email,))
            return cur.fetchone()

    def get_user_by_id(self, user_id):
        with self.conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
            return cur.fetchone()

    def check_password(self, email, password):
        user = self.get_user_by_email(email)
        if user:
            if user["lockout_count"] >= 2:
                return None
            if user["lockout_time"] > time.time():
                return None
            if bcrypt.checkpw(password.encode(), user["password"].encode()):
                return user
            self.increment_failed_attempts(email)
        return None

    def increment_failed_attempts(self, email):
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE users 
                SET failed_attempts = failed_attempts + 1,
                    lockout_time = CASE 
                        WHEN failed_attempts + 1 = 3 THEN %s 
                        ELSE lockout_time 
                    END,
                    lockout_count = CASE 
                        WHEN failed_attempts + 1 = 6 THEN lockout_count + 1 
                        ELSE lockout_count 
                    END
                WHERE email = %s
                RETURNING failed_attempts, lockout_time, lockout_count
            """, (time.time() + 30, email))
            result = cur.fetchone()
            self.conn.commit()
            if result is None:
                return {"failed_attempts": 0, "lockout_time": 0, "lockout_count": 0}
            return result

    def get_user_typing_profile(self, user_id):
        with self.conn.cursor() as cur:
            cur.execute("SELECT * FROM typing_profiles WHERE user_id = %s", (user_id,))
            profile = cur.fetchone()
            if profile:
                return {"avgDwell": profile["avg_dwell"], "avgFlight": profile["avg_flight"], "errorRate": profile["error_rate"]}
            return None

    def save_typing_dynamics(self, user_id, features):
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO typing_profiles (user_id, avg_dwell, avg_flight, error_rate, sample_count)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE
                SET avg_dwell = EXCLUDED.avg_dwell,
                    avg_flight = EXCLUDED.avg_flight,
                    error_rate = EXCLUDED.error_rate,
                    sample_count = EXCLUDED.sample_count
            """, (user_id, features["avgDwell"], features["avgFlight"], features["errorRate"], 5))
            self.conn.commit()

    def save_keystrokes(self, user_id, keystrokes):
        with self.conn.cursor() as cur:
            for ks in keystrokes:
                cur.execute("""
                    INSERT INTO keystrokes (user_id, key, press_time, release_time, dwell_time, flight_time)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (user_id, ks.get("key"), ks.get("press_time"), ks.get("release_time"),
                      ks.get("dwell_time"), ks.get("flight_time")))
            self.conn.commit()

    def update_typing_profile(self, user_id, new_features, new_samples):
        with self.conn.cursor() as cur:
            cur.execute("SELECT * FROM typing_profiles WHERE user_id = %s", (user_id,))
            profile = cur.fetchone()
            if not profile:
                print("No existing typing profile found for user! Creating new profile.")
                cur.execute("""
                    INSERT INTO typing_profiles (user_id, avg_dwell, avg_flight, error_rate, sample_count)
                    VALUES (%s, %s, %s, %s, %s)
                """, (user_id, new_features["avgDwell"], new_features["avgFlight"], new_features["errorRate"], new_samples))
                self.conn.commit()
                return True

            old_samples = profile["sample_count"]
            total_samples = old_samples + new_samples

            new_avg_dwell = (profile["avg_dwell"] * old_samples + new_features["avgDwell"] * new_samples) / total_samples
            new_avg_flight = (profile["avg_flight"] * old_samples + new_features["avgFlight"] * new_samples) / total_samples
            new_error_rate = (profile["error_rate"] * old_samples + new_features["errorRate"] * new_samples) / total_samples

            cur.execute("""
                UPDATE typing_profiles
                SET avg_dwell = %s,
                    avg_flight = %s,
                    error_rate = %s,
                    sample_count = %s
                WHERE user_id = %s
            """, (new_avg_dwell, new_avg_flight, new_error_rate, total_samples, user_id))
            self.conn.commit()
            return True

    def generate_totp_token(self, email):
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret, interval=300)
        token = totp.now()
        return token, secret

    def verify_totp_token(self, token, secret):
        totp = pyotp.TOTP(secret, interval=300)
        return totp.verify(token)

    def create_test(self, test_id, questions, assigned_ids):
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO tests (test_id, questions, assigned_ids)
                    VALUES (%s, %s, %s)
                    RETURNING test_id;
                """, (test_id, json.dumps(questions), json.dumps(assigned_ids)))
                result = cur.fetchone()
                self.conn.commit()
                return result is not None
        except psycopg2.IntegrityError:
            self.conn.rollback()
            return False

    def get_test(self, test_id):
        with self.conn.cursor() as cur:
            cur.execute("SELECT * FROM tests WHERE test_id = %s", (test_id,))
            return cur.fetchone()

    def is_test_assigned(self, test_id, user_id):
        test = self.get_test(test_id)
        if test and "assigned_ids" in test:
            assigned_ids = test["assigned_ids"]
            return user_id in assigned_ids
        return False

    def save_test_submission(self, user_id, test_id, answers, stored_confidence, test_confidence):
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO student_submissions (user_id, test_id, taken_time, stored_confidence, test_confidence, answers)
                VALUES (%s, %s, NOW(), %s, %s, %s)
                ON CONFLICT (user_id, test_id) DO UPDATE
                SET taken_time = NOW(),
                    stored_confidence = EXCLUDED.stored_confidence,
                    test_confidence = EXCLUDED.test_confidence,
                    answers = EXCLUDED.answers
                RETURNING user_id;
            """, (user_id, test_id, stored_confidence, test_confidence, json.dumps(answers)))
            result = cur.fetchone()
            self.conn.commit()
            return result is not None

    def get_assigned_test_ids(self, user_id):
        with self.conn.cursor() as cur:
            cur.execute("SELECT test_id, assigned_ids FROM tests")
            tests = cur.fetchall()
            assigned_tests = []
            for test in tests:
                if user_id in test["assigned_ids"]:
                    assigned_tests.append(test["test_id"])
            return assigned_tests

    def close(self):
        self.conn.close()

db = Database()

def send_email(to, subject, body):
    print(f"Email to {to}: Subject: {subject}, Body: {body} (simulated)")
    return True

if __name__ == "__main__":
    print("Database tables created successfully!")