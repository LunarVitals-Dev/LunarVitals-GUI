import asyncio
from bleak import BleakClient

# Update with the full 128-bit UUID for the GATT characteristic
MAC_ADDRESS = "CF:8C:8F:A7:C4:A4"# my address
#MAC_ADDRESS = "DF:9E:5B:95:6A:D9"
GATT_CHARACTERISTIC_UUID = "00002A3D-0000-1000-8000-00805F9B34FB"  # Full 128-bit UUID format

async def notification_handler(sender: int, data: bytearray):
    """
    This handler will be called when a notification is received from the peripheral.
    """
    print(f"Notification received from {sender}: {data.decode('utf-8', 'ignore')}")

async def read_nordic(client):
    """
    This function continuously reads data from the GATT characteristic.
    """
    if client.is_connected:
        print(f"Connected to {MAC_ADDRESS}")

        try:
            # Read Data from the characteristic
            response = await client.read_gatt_char(GATT_CHARACTERISTIC_UUID)
            print(f"Raw Data received: {response}")

            # Try decoding as UTF-8 first
            try:
                decoded_data = response.decode('utf-8')
                print(f"Decoded Data (UTF-8): {decoded_data}")
            except UnicodeDecodeError:
                print("UTF-8 decoding failed. Trying alternative encoding.")

                # Try Latin-1 encoding (each byte becomes a character)
                try:
                    decoded_data = response.decode('latin-1')
                    print(f"Decoded Data (Latin-1): {decoded_data}")
                except UnicodeDecodeError:
                    print("Latin-1 decoding failed. Trying ASCII encoding.")
                    
                    # Try ASCII encoding (only valid characters in ASCII)
                    try:
                        decoded_data = response.decode('ascii')
                        print(f"Decoded Data (ASCII): {decoded_data}")
                    except UnicodeDecodeError:
                        print("ASCII decoding failed. Data might be binary or in an unknown format.")
                        print(f"Hex Data: {response.hex()}")
        except Exception as e:
            print(f"Read failed: {e}")
    else:
        print("Failed to connect.")

async def main():
    """
    Main entry point for the async application.
    """
    async with BleakClient(MAC_ADDRESS) as client:
        if client.is_connected:
            services = await client.get_services()
            char = services.get_characteristic(GATT_CHARACTERISTIC_UUID)
    
            print(f"Properties: {char.properties}")

            # if "notify" in char.properties:
            #     await client.start_notify(GATT_CHARACTERISTIC_UUID, notification_handler)
            # else:
            #     print("Characteristic does not support notifications.")
            while True:
                # Continuously read data from the GATT characteristic
                await read_nordic(client)
                await asyncio.sleep(1)  # Sleep for a short interval before the next read

        else:
            print("Failed to connect.")

# Run the async function
asyncio.run(main())
