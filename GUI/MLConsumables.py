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

def process_training_data(data):
    # 1) bucket docs by (timestamp,int, activity_id)
    grouped = {}
    for doc in data:
        key = (int(doc['timestamp']), doc['activity_id'])
        sensors = grouped.setdefault(key, {})
        sensors[doc['sensor']] = doc

    # 2) build one record per complete sensor‐set
    processed = []
    for (ts, activity), sensors in grouped.items():
        pulse = sensors.get('PulseSensor')
        resp  = sensors.get('RespiratoryRate')
        temp  = sensors.get('ObjectTemp')
        accel = sensors.get('Accel')
        gyro  = sensors.get('Gyro')

        missing = [name for name, val in [
            ('PulseSensor', pulse),
            ('RespiratoryRate', resp),
            ('Temp'          , temp),
            ('Accel'         , accel),
            ('Gyro'          , gyro),
        ] if val is None]
        if missing:
            print(f"Skipping {ts,activity}: missing {missing}")
            continue

        processed.append({
            'avg_bpm'       : pulse.get('pulse_BPM'),
            'avg_resp'      : resp.get('BRPM'),
            'body_temp'     : temp.get('Celsius'),
            'step_rate'     : accel.get('step_rate'),
            'rotation_rate' : gyro.get('rotation_rate'),
            'activity_id'   : activity
        })

    df = pd.DataFrame(processed)
    if df.empty:
        print("No valid training data found.")
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
    model.fit(X_train, y_train, epochs=300, batch_size=32, validation_split=0.2, verbose=1)
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