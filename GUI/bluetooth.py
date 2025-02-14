# import asyncio
# from bleak import BleakClient

# # Replace with your device's MAC address
# NORDIC_DEVICE_MAC = "F7:98:E4:81:FC:48"  # Replace with your device's MAC address

# # Define the characteristic UUIDs for UART TX and RX (128-bit UUIDs)
# UART_RX_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"  # Updated to match the correct UART RX UUID
# UART_TX_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"  # Updated to match the correct UART TX UUID

# async def send_data_to_nordic(client, data):
#     """Write data to the Nordic device's UART TX characteristic."""
#     try:
#         # Find the characteristic with the UART_TX_UUID and write data to it
#         for service in client.services:
#             for characteristic in service.characteristics:
#                 if characteristic.uuid == UART_TX_UUID:
#                     await client.write_gatt_char(characteristic, data.encode())  # Send data as bytes
#                     print(f"Sent: {data}")
#                     return
#         print("UART TX characteristic not found!")
#     except Exception as e:
#         print(f"Error sending data: {e}")

# async def on_uart_rx_data(sender: int, data: bytearray):
#     """Callback function to handle incoming data from the Nordic device."""
#     print(f"Received from Nordic: {data.decode('utf-8', errors='ignore')}")

# async def discover_services_and_send_data():
#     async with BleakClient(NORDIC_DEVICE_MAC) as client:
#         print(f"Connected: {client.is_connected}")
#         services = client.services  # Access the services of the connected device
#         for service in services:
#             print(f"Service UUID: {service.uuid}")
#             for characteristic in service.characteristics:
#                 print(f"  Characteristic UUID: {characteristic.uuid}")
#                 if characteristic.uuid == UART_TX_UUID:
#                     print("Found UART TX characteristic")
#                 elif characteristic.uuid == UART_RX_UUID:
#                     print("Found UART RX characteristic")
#                     # Subscribe to notifications for incoming data on UART RX
#                     await client.start_notify(characteristic, on_uart_rx_data)

#         # Keep the connection open and send data from terminal
#         try:
#             while True:
#                 # Wait for user input
#                 user_input = input("Enter message to send to Nordic: ")
#                 if user_input.lower() == "exit":
#                     print("Exiting...")
#                     break
#                 await send_data_to_nordic(client, user_input)
#                 await asyncio.sleep(1)  # Sleep to prevent blocking the event loop
#         except KeyboardInterrupt:
#             print("Disconnected by user.")
#         finally:
#             # Ensure notifications are stopped when disconnecting
#             for service in client.services:
#                 for characteristic in service.characteristics:
#                     if characteristic.uuid == UART_RX_UUID:
#                         await client.stop_notify(characteristic)

# if __name__ == "__main__":
#     asyncio.run(discover_services_and_send_data())

import asyncio
from bleak import BleakClient
from pymongo import MongoClient
import os
import json
from dotenv import load_dotenv
import sys
import time

# Load environment variables
load_dotenv()

# Replace with your device's MAC address
NORDIC_DEVICE_MAC = "F7:98:E4:81:FC:48"

# Define the characteristic UUIDs for UART TX and RX (128-bit UUIDs)
UART_RX_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
UART_TX_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"

# MongoDB setup
try:
    client = MongoClient(os.getenv("MONGODB_URI"))
    db = client["LunarVitalsDB"]
    collection = db["sensor_data"]
except Exception as e:
    print(f"Error connecting to MongoDB: {e}")
    sys.exit(1)

async def send_data_to_nordic(client, data):
    """Write data to the Nordic device's UART TX characteristic."""
    try:
        # Find the characteristic with the UART_TX_UUID and write data to it
        for service in client.services:
            for characteristic in service.characteristics:
                if characteristic.uuid == UART_TX_UUID:
                    await client.write_gatt_char(characteristic, data.encode())  # Send data as bytes
                    print(f"Sent: {data}")
                    return
        print("UART TX characteristic not found!")
    except Exception as e:
        print(f"Error sending data: {e}")

async def on_uart_rx_data(sender: int, data: bytearray):
    """Callback function to handle incoming data from the Nordic device."""
    message = data.decode('utf-8', errors='ignore')
    print(f"Received from Nordic: {message}")

    # Store the received data in MongoDB
    try:
        json_data = json.loads(message)
        json_data['timestamp'] = time.time()
        collection.insert_one(json_data)
        print("Data inserted into MongoDB")
    except Exception as e:
        print(f"Error inserting data into MongoDB: {e}")

async def discover_services_and_send_data():
    async with BleakClient(NORDIC_DEVICE_MAC) as client:
        print(f"Connected: {client.is_connected}")
        services = client.services  # Access the services of the connected device
        for service in services:
            print(f"Service UUID: {service.uuid}")
            for characteristic in service.characteristics:
                print(f"  Characteristic UUID: {characteristic.uuid}")
                if characteristic.uuid == UART_TX_UUID:
                    print("Found UART TX characteristic")
                elif characteristic.uuid == UART_RX_UUID:
                    print("Found UART RX characteristic")
                    # Subscribe to notifications for incoming data on UART RX
                    await client.start_notify(characteristic, on_uart_rx_data)

        # Keep the connection open and send data from terminal
        try:
            while True:
                # Wait for user input
                user_input = input("Enter message to send to Nordic: ")
                if user_input.lower() == "exit":
                    print("Exiting...")
                    break
                await send_data_to_nordic(client, user_input)
                await asyncio.sleep(1)  # Sleep to prevent blocking the event loop
        except KeyboardInterrupt:
            print("Disconnected by user.")
        finally:
            # Ensure notifications are stopped when disconnecting
            for service in client.services:
                for characteristic in service.characteristics:
                    if characteristic.uuid == UART_RX_UUID:
                        await client.stop_notify(characteristic)

if __name__ == "__main__":
    asyncio.run(discover_services_and_send_data())