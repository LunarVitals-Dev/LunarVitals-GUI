import os
import joblib
import numpy as np
import pandas as pd
import tensorflow as tf
from tensorflow.keras import layers
from pymongo import MongoClient
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.model_selection import train_test_split
from dotenv import load_dotenv

def connect_to_mongodb():
    """Connect to MongoDB using environment variable settings."""
    try:
        load_dotenv()
        client = MongoClient(os.getenv("MONGODB_URI"))
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
    """
    Process raw MongoDB data into a DataFrame by grouping documents that share the same
    (rounded) timestamp and activity_id, then merging the sensor fields from each group.
    
    Each training sample is expected to provide:
      - 'RespiratoryRate' with the nested key 'BRPM',
      - 'MLX_ObjectTemperature' with the nested key 'celsius',
      - 'activity_id'.
    
    Documents that do not contribute both sensor values will be skipped.
    """
    # Group documents by a key based on the integer part of the timestamp and activity_id.
    grouped = {}
    for doc in data:
        key = (int(doc['timestamp']), doc['activity_id'])
        group = grouped.setdefault(key, {})
        for k, v in doc.items():
            if k in ('_id', 'timestamp'):
                continue
            group[k] = v
        group['activity_id'] = doc['activity_id']

    # Build the training samples from the grouped data.
    processed = []
    for key, record in grouped.items():
        # Check for the required sensor groups.
        resp_data = record.get('RespiratoryRate')
        temp_data = record.get('MLX_ObjectTemperature')
        if resp_data is None or temp_data is None:
            # Skip this group if one of the sensors is missing.
            continue
        
        brpm = resp_data.get('BRPM')
        celsius = temp_data.get('Celsius')
        if brpm is not None and celsius is not None:
            processed.append({
                'avg_bpm': brpm,          # Using BRPM from RespiratoryRate.
                'body_temp': celsius,      # Using Celsius from MLX_ObjectTemperature.
                'activity_id': record.get('activity_id')
            })
        else:
            print("Grouped record missing required nested keys:", record)
            
    if not processed:
        print("No valid training data found.")
    return pd.DataFrame(processed)

def prepare_features_labels(df):
    """Create feature and label arrays, applying scaling and one-hot encoding."""
    # Extract features and labels
    X = df[['avg_bpm', 'body_temp']].values
    y = df['activity_id'].values.reshape(-1, 1)

    # Feature scaling
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # One-hot encoding of labels
    encoder = OneHotEncoder(sparse=False, handle_unknown='ignore')
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
        layers.InputLayer(shape=(2,)),  # Two features: avg_bpm and body_temp
        layers.Dense(64, activation='relu'),
        layers.Dense(32, activation='relu'),
        layers.Dense(num_classes, activation='softmax')
    ])

    model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
                  loss='categorical_crossentropy',
                  metrics=['accuracy'])

    print("Starting training...")
    model.fit(X_train, y_train, epochs=20, batch_size=32, validation_split=0.2, verbose=1)
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
