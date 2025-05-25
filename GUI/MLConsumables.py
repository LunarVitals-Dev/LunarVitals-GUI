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
from sklearn.utils.class_weight import compute_class_weight

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
    """
    Turn your flat Mongo documents into a DataFrame with one row per timestamp,
    pulling out exactly the five features we need.
    """
    # 1) DataFrame from list of dicts
    df = pd.DataFrame(data)

    # 2) Rename the columns to match our feature names
    df = df.rename(columns={
        "pulse_BPM": "avg_bpm",
        "BRPM":      "avg_resp",
        "s_rate":    "step_rate",
        "r_rate":    "rotation_rate"
    })

    # 3) Keep only the columns we’ll train on, plus the label
    df = df[[
        "activity_id",
        "avg_bpm",
        "avg_resp",
        "step_rate",
        "rotation_rate"
    ]]

    df = df.dropna()

    return df

def prepare_features_labels(df):
    # Extract features and labels
    X = df[['avg_bpm','avg_resp','step_rate','rotation_rate']].values
    y_raw = df['activity_id'].values     

    # Feature scaling
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # One-hot encoding of labels
    encoder = OneHotEncoder(sparse_output=False, handle_unknown='ignore')
    y_encoded = encoder.fit_transform(y_raw.reshape(-1, 1))

    return X_scaled, y_encoded, scaler, encoder, y_raw

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

    X, y, scaler, encoder, y_raw = prepare_features_labels(df)
    classes = encoder.categories_[0]
    weights = compute_class_weight('balanced', classes=classes, y=y_raw)

    # round each weight to 4 decimals and cast to float
    class_weight_dict = {
        cls: round(float(w), 4)
        for cls, w in zip(classes, weights)
    }

    print("Class weights by name:", class_weight_dict)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    num_classes = y_train.shape[1]
    model = tf.keras.Sequential([
        layers.InputLayer(shape=(4,)),
        layers.BatchNormalization(),
        layers.Dense(128, activation='relu'),
        layers.Dense(96,  activation='relu'),
        layers.Dense(64, activation='relu'),
        layers.Dense(num_classes, activation='softmax')
    ])

    model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
                  loss='categorical_crossentropy',
                  metrics=['accuracy'])

    print("Starting training...")
    model.fit(X_train, y_train, epochs=300, batch_size=32, validation_split=0.2, class_weight=class_weight_dict, verbose=1)
    loss, acc = model.evaluate(X_test, y_test, verbose=1)
    print(f"Test Loss: {loss:.4f}, Test Accuracy: {acc:.4f}")
    
    base_acc = model.evaluate(X_test, y_test, verbose=0)[1]
    
    feature_names = ['avg_bpm', 'avg_resp', 'step_rate', 'rotation_rate']

    for i, name in enumerate(feature_names):
        X_perm = X_test.copy()
        np.random.shuffle(X_perm[:, i])           
        acc = model.evaluate(X_perm, y_test, verbose=0)[1]
        print(f"{name:<15}  acc = {base_acc - acc:.4f}") # how badly accuracy suffers without it

    # Save the trained model and preprocessing objects for later use in the PyQt app
    model.save("activity_model_mongodb.keras")
    joblib.dump(scaler, "feature_scaler_mongodb.joblib")
    joblib.dump(encoder, "activity_encoder_mongodb.joblib")
    print("Model and preprocessing objects saved successfully.")

    return model, scaler, encoder

if __name__ == '__main__':
    train_activity_model()