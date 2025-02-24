from flask import Flask, render_template, jsonify, request, redirect, url_for, Response, session, flash, jsonify
from flask_socketio import SocketIO
import subprocess
import json
import random
import time
import os
import can
from flask_session import Session

# Cấu hình CAN: thay '/dev/ttyACM0' (hoặc '/dev/ttyUSB0') và bitrate cho đúng với adapter
SERIAL_PORT = "/dev/ttyACM1"  
BITRATE = 500000

# Tạo bus CAN toàn cục để sử dụng trong Flask
bus = can.interface.Bus(bustype='slcan', channel=SERIAL_PORT, bitrate=BITRATE)

app = Flask(__name__)
app.secret_key = "supersecretkey"  # 🔑 Khóa bảo mật cho session
app.config["SESSION_TYPE"] = "filesystem"
Session(app)
socketio = SocketIO(app)

# 🔐 Thông tin tài khoản mặc định
users = {
    "admin": "1",  # 🔹 Bạn có thể đổi mật khẩu này
}

IGNORED_USB_NAMES = ["Standard Microsystems Corp.", "Linux Foundation", "root hub"]
device_status = {}  # Lưu trạng thái kết nối của thiết bị
device_custom_names = {}  # Lưu tên thiết bị tùy chỉnh
device_settings = {}  # Lưu settings riêng theo từng thiết bị

# Dữ liệu settings mặc định
default_settings = {
    "CAN Identifier": "0x01",
    "CAN Controller": "1122334455667788",
    "Baud rate": "500 kbs",
    "Mode": "NORMAL"
}

# Load dữ liệu từ file JSON
def load_json_data(filename, default_data):
    try:
        with open(filename, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default_data

# Ghi dữ liệu vào file JSON
def save_json_data(filename, data):
    with open(filename, "w") as f:
        json.dump(data, f, indent=4)

# Load dữ liệu từ file
device_custom_names = load_json_data("device_names.json", {})
device_settings = load_json_data("device_settings.json", {})

def scan_usb_devices():
    """Lấy danh sách thiết bị USB thực"""
    try:
        output = subprocess.check_output("lsusb", shell=True).decode("utf-8")
        devices = []

        for index, line in enumerate(output.strip().split("\n"), start=1):
            parts = line.split()
            if len(parts) < 6:
                continue

            device = parts[3].strip(":")
            name = " ".join(parts[6:])  # Lấy tên thiết bị mặc định

            if any(ignored in name for ignored in IGNORED_USB_NAMES):
                continue
            
            # Kiểm tra nếu có tên tùy chỉnh
            name = device_custom_names.get(device, name)
            status = device_status.get(device, "Disconnected")

            devices.append({
                "no": f"{index:03d}",
                "port": device,
                "name": name,
                "status": status
            })

        return devices
    except Exception as e:
        return [{"error": str(e)}]

# 🔒 Middleware kiểm tra đăng nhập
def login_required(f):
    def wrap(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    wrap.__name__ = f.__name__
    return wrap

@app.route("/")
def home():
    return redirect(url_for("devices"))

@app.route("/login", methods=["GET", "POST"])
def login():
    """Trang đăng nhập"""
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        if username in users and users[username] == password:
            session["user"] = username
            flash("Login successful!", "success")
            return redirect(url_for("devices"))
        else:
            flash("Invalid username or password", "danger")
    
    return render_template("login.html")

@app.route("/logout")
def logout():
    """Đăng xuất"""
    session.pop("user", None)
    flash("Logged out successfully", "success")
    return redirect(url_for("login"))

@app.route("/devices")
@login_required
def devices():
    """Trang Devices hiển thị danh sách thiết bị"""
    return render_template("index.html", devices=scan_usb_devices(), title="Devices")

@app.route("/settings")
@login_required
def settings():
    """Trang Settings hiển thị danh sách thiết bị"""
    return render_template("settings.html", device_names=list(device_custom_names.values()), title="Settings")

@app.route("/operations")
@login_required
def operations():
    return render_template("operations.html", settings=device_settings, title="Operations")

def stream_logs():
    """Chạy candump để lấy dữ liệu logs CAN bus"""
    process = subprocess.Popen(["candump", "can0"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    # Đọc logs từng dòng
    for line in iter(process.stdout.readline, ''):
        print(f"Log: {line.strip()}")  # Debug trên terminal
        socketio.emit("log_update", {"log": line.strip()})  # Gửi logs qua WebSocket
    
    process.stdout.close()
    process.wait()

@app.route("/start_logs")
def start_logs():
    """Bắt đầu nhận logs từ CAN bus"""
    socketio.start_background_task(target=stream_logs)
    return "Logs streaming started"

# ✅ API cập nhật tên thiết bị
@app.route("/api/update_device_name", methods=["POST"])
def update_device_name():
    data = request.json
    port = data.get("port")
    new_name = data.get("new_name")

    if not port or not new_name:
        return jsonify({"error": "Missing port or new name"}), 400

    device_custom_names[port] = new_name  
    save_json_data("device_names.json", device_custom_names)  

    return jsonify({"message": f"Device {port} renamed to {new_name}"})

# ✅ API cập nhật trạng thái thiết bị
@app.route("/api/device_status/<port>", methods=["POST"])
def update_device_status(port):
    action = request.json.get("action")
    if action == "start":
        device_status[port] = "Connected"
    elif action == "stop":
        device_status[port] = "Disconnected"
    else:
        return jsonify({"error": "Invalid action"}), 400

    return jsonify({"message": f"Device {port} updated", "status": device_status[port]})

# ✅ API cập nhật trạng thái hệ thống toàn cục
@app.route("/api/device_status/global", methods=["POST"])
def update_global_device_status():
    action = request.json.get("action")
    if action == "start":
        device_status["global"] = "Running"
    elif action == "stop":
        device_status["global"] = "Idle"
    else:
        return jsonify({"error": "Invalid action"}), 400

    return jsonify({"message": f"Device set to {device_status['global']}!"})

# ✅ API quét danh sách thiết bị USB
@app.route("/api/scan_usb")
def api_scan_usb():
    return jsonify(scan_usb_devices())

# ✅ API gửi dữ liệu CAN bus
@app.route("/api/send_data/<port>", methods=["POST"])
def send_data_to_device(port):
    try:
        data = request.json
        can_id = data.get("can_id")
        payload = data.get("payload")

        if not can_id or not payload:
            return jsonify({"error": "Missing CAN ID or Payload"}), 400

        command = f"cansend can0 {can_id}#{payload}"
        subprocess.run(command, shell=True, check=True)

        return jsonify({"message": f"CAN frame {can_id}#{payload} sent successfully!"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ✅ API lấy danh sách thiết bị
@app.route("/api/device_names")
def get_device_names():
    return jsonify(list(device_custom_names.values()))

# ✅ API lấy settings của từng thiết bị
@app.route("/api/get_settings/<device_name>")
def get_device_settings(device_name):
    """API trả về settings của một thiết bị cụ thể"""
    return jsonify(device_settings.get(device_name, default_settings))

# ✅ API cập nhật settings theo từng thiết bị
@app.route("/api/update_settings/<device_name>", methods=["POST"])
def update_device_settings(device_name):
    """API cập nhật settings cho thiết bị cụ thể"""
    data = request.json
    device_settings[device_name] = data
    save_json_data("device_settings.json", device_settings)
    return jsonify({"message": f"Settings for {device_name} updated successfully!"})

# ✅ API xuất JSON chỉ chứa các cài đặt đã chỉnh sửa
@app.route("/api/export_settings/<device_name>")
@login_required
def export_device_settings(device_name):
    settings = device_settings.get(device_name, {})
    filtered_settings = {k: v for k, v in settings.items() if v != default_settings.get(k)}

    response = Response(
        json.dumps(filtered_settings, indent=4),
        mimetype="application/json",
        headers={"Content-Disposition": f"attachment;filename={device_name}_settings.json"}
    )
    return response
@socketio.on("connect")
def handle_connect():
    print("Client connected")

@socketio.on("disconnect")
def handle_disconnect():
    print("Client disconnected")

@app.route("/api/can_waveform")
def can_waveform():
    """Trả về dữ liệu mô phỏng CAN waveform (tạm thời)"""
    fake_data = {"time": list(range(10)), "voltage": [random.uniform(0, 5) for _ in range(10)]}
    return jsonify(fake_data)
@app.route('/')
def index():
    # Trang chính có form để nhập ID, data
    return render_template('index.html')

@app.route('/send_can', methods=['POST'])
def send_can():
    """
    Hàm nhận dữ liệu từ form và gửi CAN frame.
    """
    try:
        # Lấy tham số từ form
        can_id_str = request.form.get('can_id', '0x123')  # Chuỗi ID, ví dụ "0x123" hoặc "291"
        can_data_str = request.form.get('can_data', '')   # Chuỗi data, ví dụ "11 22 33 44" hoặc "11223344"

        print(f"Received can_id: {can_id_str}, can_data: {can_data_str}")  # Debug log

        # Chuyển can_id_str -> số nguyên
        #   - Nếu can_id_str có '0x' thì dùng int(can_id_str, 16) 
        #   - Nếu là thập phân thì int(can_id_str)
        if can_id_str.lower().startswith('0x'):
            can_id = int(can_id_str, 16)
        else:
            can_id = int(can_id_str)

        # Chuyển can_data_str -> list byte
        #   Ví dụ: "11 22 33 44" -> [0x11, 0x22, 0x33, 0x44]
        #   Hoặc "11223344" -> [0x11, 0x22, 0x33, 0x44]
        data_bytes = []
        # Cách 1: Tách theo khoảng trắng
        if ' ' in can_data_str:
            parts = can_data_str.split()
            for p in parts:
                data_bytes.append(int(p, 16))
        else:
            # Cách 2: Chuỗi dính liền, cắt mỗi 2 ký tự
            # Cần độ dài chẵn
            can_data_str = can_data_str.replace("0x", "")  # nếu có "0x"
            # Đảm bảo độ dài chuỗi
            if len(can_data_str) % 2 != 0:
                return jsonify({"error": "Chuỗi data không hợp lệ (độ dài phải chẵn)."}), 400

            for i in range(0, len(can_data_str), 2):
                byte_str = can_data_str[i:i+2]
                data_bytes.append(int(byte_str, 16))
        print(f"Processed can_id: {can_id}, data: {data_bytes}")  # Debug log
        # Tạo CAN message
        msg = can.Message(
            arbitration_id=can_id,
            data=data_bytes,
            is_extended_id=False  # Nếu bạn cần extended ID thì để True
        )

        # Gửi message
        bus.send(msg)
        print(f"Gửi CAN: ID={hex(can_id)}, data={data_bytes}")
        return jsonify({"status": "ok", "id": hex(can_id), "data": data_bytes})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

        
# Tìm port của USB CAN
@app.route("/api/get_can_ports", methods=["GET"])
def get_can_ports():
    """
    Trả về danh sách các cổng CAN từ Raspberry Pi.
    """
    try:
        result = subprocess.check_output("ls /dev/ttyACM*", shell=True, text=True).strip()
        ports = result.split("\n") if result else []
        return jsonify({"ports": ports})
    except subprocess.CalledProcessError:
        return jsonify({"ports": []})  # Trả về danh sách rỗng nếu không có cổng nào

if __name__ == "__main__":
    print(f"Khởi động Flask, kết nối CAN trên {SERIAL_PORT} (bitrate={BITRATE})")
    app.run(host="0.0.0.0", port=5000, debug=True)
