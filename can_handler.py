import can

SERIAL_PORT = "/dev/ttyACM0"  # Cổng USB to CAN
BITRATE = 500000  # Tốc độ truyền

class CanHandler:
    def __init__(self):
        self.bus = None

    def connect_can(self):
        """Kết nối CAN Bus"""
        try:
            self.bus = can.interface.Bus(bustype='slcan', channel=SERIAL_PORT, bitrate=BITRATE)
            print(f"✅ Connected to CAN on {SERIAL_PORT} (Baudrate: {BITRATE})")
        except Exception as e:
            print(f"❌ CAN Connection Failed: {e}")

    def send_can_message(self, text):
        """Chuyển đổi text thành CAN frame và gửi đi"""
        try:
            self.connect_can()
            
            # Ví dụ: "Speed 100" -> ID 0x100, Data = [100]
            parts = text.split()
            if len(parts) != 2:
                return {"error": "Invalid format. Use 'Speed 100'."}

            command, value = parts[0], int(parts[1])

            if command.lower() == "speed":
                can_id = 0x100  # Giả sử ID cho Speed là 0x100
            else:
                return {"error": "Unknown command"}

            # Định dạng data (1 byte)
            data = [value]

            # Tạo CAN frame
            msg = can.Message(
                arbitration_id=can_id,
                data=data,
                is_extended_id=False
            )

            self.bus.send(msg)
            print(f"📤 Sent CAN Frame: ID={hex(can_id)}, Data={data}")
            return {"message": "CAN message sent!", "can_id": hex(can_id), "data": data}
        except Exception as e:
            return {"error": str(e)}

# Singleton CAN Controller
can_handler = CanHandler()
