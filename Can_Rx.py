import can

# Cấu hình cổng CAN
SERIAL_PORT = "COM7"
BITRATE = 500000

# Định nghĩa ID tương ứng
CAN_ID_MAP = {
    0x123: ("Speed 🚀", "km/h"),
    0x124: ("Battery 🔋", "%"),
    0x125: ("Temperature 🌡️", "°C")
}

try:
    # Kết nối với CAN bus
    bus = can.interface.Bus(bustype='slcan', channel=SERIAL_PORT, bitrate=BITRATE)
    print(f"✅ Listening for CAN data on {SERIAL_PORT} (Baudrate: {BITRATE})")

    while True:
        # Nhận dữ liệu với timeout 5 giây
        message = bus.recv(timeout=5)

        if message:
            can_id = message.arbitration_id
            data_bytes = message.data

            if can_id in CAN_ID_MAP:
                category, unit = CAN_ID_MAP[can_id]

                # Giải mã dữ liệu chính xác theo số byte nhận được
                if len(data_bytes) == 1:
                    data_value = int(data_bytes[0])  # Nếu 1 byte, lấy giá trị trực tiếp
                else:
                    data_value = int.from_bytes(data_bytes, byteorder="big")  # Nếu nhiều byte, ghép thành số

                print(f"📩 Received: {category} - Value: {data_value} {unit}")
            else:
                print(f"⚠️ Unknown CAN ID={can_id}, Raw Data={data_bytes.hex()}")

        else:
            print("⚠️ No CAN data received (Timeout).")

except can.CanError as e:
    print(f"❌ CAN Error: {e}")

except KeyboardInterrupt:
    print("\n🛑 Stopping CAN listener...")

finally:
    # Tắt kết nối CAN đúng cách
    if 'bus' in locals() and bus is not None:
        bus.shutdown()
        print("🔌 CAN bus connection closed.")
