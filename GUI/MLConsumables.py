import os

os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'

import joblib
import numpy as np
import pandas as pd
import tensorflow as tf
from tensorflow.keras import layers
from pymongo import MongoClient
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.model_selection import train_test_split

def connect_to_mongodb():
    MONGODB_URI = "mongodb+srv://LunarVitals:lunarvitals1010@peakfitness.i5blp.mongodb.net/"
    
    try:
        client = MongoClient(MONGODB_URI)
        db = client["LunarVitalsDB"]
        collection = db["sensor_data"]
        return collection
    except Exception as e:
        print(f"Error connecting to MongoDB: {e}")
        return None

def fetch_training_data():
    """Retrieve training data stored in MongoDB."""
    collection = connect_to_mongodb()
    if collection is None:
        return None
    cursor = collection.find({}).sort('timestamp', 1)
    data = list(cursor)
    if data:
        print(f"Fetched {len(data)} training documents from MongoDB.")
    else:
        print("No training data retrieved from MongoDB.")
    
    return data

def process_training_data(data, max_span=2.0):

    sensor_map = {
        'PulseSensor':     ('avg_bpm',       'pulse_BPM'),
        'RespiratoryRate': ('avg_resp',      'BRPM'),
        'AmbientTemp':     ('body_temp',     'Celsius'),
        'Accel':           ('step_rate',     's_rate'),
        'Gyro':            ('rotation_rate', 'r_rate'),
    }
    required = set(sensor_map)

    # sort all docs by timestamp
    docs = sorted(data, key=lambda d: d['timestamp'])
    processed = []

    current_group    = {}
    current_activity = None
    group_start_ts   = None

    for doc in docs:
        s   = doc.get('sensor')
        act = doc.get('activity_id')
        ts  = doc.get('timestamp')

        # ignore sensors we don't care about
        if s not in sensor_map:
            continue

        # if this doc lacks its required field, skip it
        _, fld = sensor_map[s]
        if fld not in doc:
            print(f"Skipping {s} at {ts:.3f}: missing {fld}")
            continue

        # start new group on activity change or if group is empty
        if act != current_activity or not current_group:
            current_group    = {}
            current_activity = act
            group_start_ts   = ts

        # if we’ve waited too long, drop and restart
        if ts - group_start_ts > max_span:
            current_group    = {}
            current_activity = act
            group_start_ts   = ts

        # stash this reading
        current_group[s] = doc

        # once we have them all, build a training record
        if required.issubset(current_group):
            rec = {'activity_id': current_activity}
            for sen, (feat, fld) in sensor_map.items():
                rec[feat] = current_group[sen][fld]
            processed.append(rec)

            # reset for the next quintuple
            current_group    = {}
            current_activity = None
            group_start_ts   = None

    df = pd.DataFrame(processed)
    return df

def prepare_features_labels(df):
    # Extract features and labels
    df = df.dropna(subset=[
        'avg_bpm','avg_resp','body_temp','step_rate','rotation_rate'
    ])
    X = df[['avg_bpm','avg_resp','body_temp','step_rate','rotation_rate']].values
    y = df['activity_id'].values.reshape(-1, 1)    

    # Feature scaling
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # One-hot encoding of labels
    encoder = OneHotEncoder(sparse_output=False, handle_unknown='ignore')
    y_encoded = encoder.fit_transform(y)

    return X_scaled, y_encoded, scaler, encoder

def train_activity_model():
    """Fetch training data, process it, train the model, and save artifacts."""
    data = fetch_training_data()
    if data is None or len(data) == 0:
        print("No training data found in MongoDB. Exiting training.")
        return None, None, None

    df = process_training_data(data)
    if df.empty:
        print("Processed training DataFrame is empty. Exiting training.")
        return None, None, None

    X, y, scaler, encoder = prepare_features_labels(df)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    num_classes = y_train.shape[1]
    model = tf.keras.Sequential([
        layers.InputLayer(shape=(5,)), 
        layers.Dense(64, activation='relu'),
        layers.Dense(32, activation='relu'),
        layers.Dense(num_classes, activation='softmax')
    ])

    model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
                  loss='categorical_crossentropy',
                  metrics=['accuracy'])

    print("Starting training...")
    model.fit(X_train, y_train, epochs=500, batch_size=32, validation_split=0.2, verbose=1)
    loss, acc = model.evaluate(X_test, y_test, verbose=1)
    print(f"Test Loss: {loss:.4f}, Test Accuracy: {acc:.4f}")

    # Save the trained model and preprocessing objects for later use in the PyQt app
    model.save("activity_model_mongodb.keras")
    joblib.dump(scaler, "feature_scaler_mongodb.joblib")
    joblib.dump(encoder, "activity_encoder_mongodb.joblib")
    print("Model and preprocessing objects saved successfully.")

    return model, scaler, encoder

if __name__ == '__main__':
    train_activity_model()