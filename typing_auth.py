# typing_auth.py
from pynput import keyboard
import time
import pandas as pd

def typing_auth(user_id, mode, expected_phrase="thequickbrownfox", samples_needed=5):
    print(f"User {user_id}: Type '{expected_phrase}' {samples_needed} time{'s' if samples_needed > 1 else ''} (press Enter after each):")
    all_events = []
    valid_samples = 0
    total_errors = 0

    def on_press(key):
        nonlocal last_press_time
        current_time = time.time()
        try:
            if hasattr(key, 'char'):
                last_press_time = current_time
                current_events.append({'key': key.char, 'press_time': current_time})
        except AttributeError:
            pass

    def on_release(key):
        nonlocal last_release_time
        current_time = time.time()
        try:
            if hasattr(key, 'char'):
                last_release_time = current_time
                for event in reversed(current_events):
                    if event['key'] == key.char and 'release_time' not in event:
                        event['release_time'] = current_time
                        break
        except AttributeError:
            pass

    for i in range(samples_needed):
        print(f"{i+1}. ", end="")
        current_events = []
        last_press_time = None
        last_release_time = None

        with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
            typed = input()
            listener.join(0.1)

        if typed == expected_phrase:
            if len(current_events) >= len(expected_phrase):
                all_events.extend(current_events[:len(expected_phrase)])
                valid_samples += 1
            else:
                total_errors += len(expected_phrase)
        else:
            errors = sum(1 for a, b in zip(typed, expected_phrase) if a != b)
            errors += max(0, len(expected_phrase) - len(typed))
            total_errors += errors

    total_possible_chars = len(expected_phrase) * samples_needed
    error_rate = total_errors / total_possible_chars if total_possible_chars > 0 else 1.0
    error_rate = max(0.0, min(1.0, error_rate))

    if all_events:
        df = pd.DataFrame(all_events)
        df['dwell_time'] = df['release_time'] - df['press_time']
        df['flight_time'] = df['press_time'].shift(-1) - df['release_time']
        avg_dwell = df['dwell_time'].mean() * 1000 if not df['dwell_time'].isna().all() else 0
        avg_flight = df['flight_time'].mean() * 1000 if not df['flight_time'].isna().all() else 0

        for i, event in enumerate(all_events):
            event['dwell_time'] = df['dwell_time'][i] if not pd.isna(df['dwell_time'][i]) else 0
            event['flight_time'] = df['flight_time'][i] if not pd.isna(df['flight_time'][i]) else None
    else:
        avg_dwell, avg_flight = 0, 0

    features = {
        "avgDwell": avg_dwell,
        "avgFlight": avg_flight,
        "errorRate": error_rate
    }
    return {"samples": valid_samples, "features": features, "keystrokes": all_events}