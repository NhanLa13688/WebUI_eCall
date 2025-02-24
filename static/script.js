document.addEventListener("DOMContentLoaded", function () {
    // 🟢 Load CAN ports và USB devices khi trang được tải
    if (document.getElementById("canPort")) {
        loadCanPorts();
    }
    if (document.getElementById("usb-list")) {
        scanDevices();
    }
    if (document.getElementById("scanButton")) {
        document.getElementById("scanButton").addEventListener("click", scanAllDevices);
    }
    if (document.getElementById("saveSettings")) {
        document.getElementById("saveSettings").addEventListener("click", saveCanSettings);
    }

    // 🟢 Lắng nghe sự kiện submit cho tất cả các form CAN
    document.querySelectorAll(".canForm").forEach(form => {
        form.addEventListener('submit', handleFormSubmit);
    });
});

// 🟢 Xử lý sự kiện submit của các form CAN
async function handleFormSubmit(e) {
    e.preventDefault();

    const form = e.target;
    const canId = form.querySelector('.can-id').value;
    const canData = form.querySelector('.can-data').value;
    
    try {
        // Gửi dữ liệu qua API
        const result = await sendCanData(canId, canData);

        // Hiển thị kết quả gửi CAN
        const resultDiv = form.querySelector('.result');
        resultDiv.style.display = "block";
        if (result.error) {
            resultDiv.innerHTML = `❌ Error: ${result.error}`;
            resultDiv.classList.add('alert-danger');
            resultDiv.classList.remove('alert-success');
        } else {
            resultDiv.innerHTML = `✅ Sent CAN: ID=${result.id}, DATA=${result.data}`;
            resultDiv.classList.add('alert-success');
            resultDiv.classList.remove('alert-danger');
        }
    } catch (error) {
        console.error('Error sending CAN data:', error);
    }
}

// 🟢 Gửi dữ liệu CAN
async function sendCanData(canId, canData) {
    const response = await fetch('/send_can', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ can_id: canId, can_data: canData })
    });

    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || 'Unknown error');
    }
    return await response.json();
}

// 🟢 Scan USB devices and update list
async function scanDevices() {
    let tableBody = document.getElementById("usb-list");
    if (!tableBody) return;

    tableBody.innerHTML = '<tr><td colspan="5" class="text-center">🔄 Scanning devices...</td></tr>';

    try {
        const response = await fetch("/api/scan_usb");
        const data = await response.json();

        tableBody.innerHTML = data.length === 0 ?
            '<tr><td colspan="5" class="text-center">❌ No USB devices found</td></tr>' :
            data.map((device, index) => `
                <tr>
                    <td>${index + 1}</td>
                    <td>${device.port}</td>
                    <td>${device.name}</td>
                    <td><span class="${device.status === 'Connected' ? 'text-success' : 'text-danger'}">${device.status}</span></td>
                    <td>
                        <button class="btn btn-sm btn-success" onclick="updateDeviceStatus('${device.port}', 'start')">Start</button>
                        <button class="btn btn-sm btn-danger" onclick="updateDeviceStatus('${device.port}', 'stop')">Stop</button>
                        <button class="btn btn-sm btn-outline-secondary" onclick="updateDeviceName('${device.port}')">🖊</button>
                    </td>
                </tr>
            `).join('');
    } catch (error) {
        console.error("Error scanning USB:", error);
        tableBody.innerHTML = '<tr><td colspan="5" class="text-center text-danger">❌ Error scanning USB devices</td></tr>';
    }
}

// 🟢 Load CAN ports from API
async function loadCanPorts() {
    let canPortDropdown = document.getElementById("canPort");
    if (!canPortDropdown) return;

    canPortDropdown.innerHTML = '<option>🔄 Loading CAN ports...</option>';

    try {
        const response = await fetch("/api/get_can_ports");
        const data = await response.json();

        canPortDropdown.innerHTML = data.ports.length === 0 ?
            '<option value="">❌ No CAN port found</option>' :
            data.ports.map(port => `<option value="${port}">${port}</option>`).join('');
    } catch (error) {
        console.error("Error loading CAN ports:", error);
        canPortDropdown.innerHTML = '<option value="">❌ Error loading CAN ports</option>';
    }
}

// 🟢 Scan both USB devices and CAN ports
async function scanAllDevices() {
    await Promise.all([scanDevices(), loadCanPorts()]);
}

// 🟢 Update device status (Start/Stop)
async function updateDeviceStatus(port, action) {
    try {
        const response = await fetch(`/api/device_status/${port}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ action })
        });
        const data = await response.json();
        alert(data.message);
        await scanDevices(); // Refresh device list after updating status
    } catch (error) {
        console.error("Error updating status:", error);
    }
}

// 🟢 Update device name
async function updateDeviceName(port) {
    let newName = prompt("Enter a new name for the device:");
    if (!newName) return;

    try {
        const response = await fetch("/api/update_device_name", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ port, new_name: newName })
        });
        const data = await response.json();
        if (data.error) {
            alert("Error: " + data.error);
        } else {
            await scanDevices(); // Refresh device list after renaming
        }
    } catch (error) {
        console.error("Error updating device name:", error);
    }
}

// 🟢 Save CAN configuration settings
async function saveCanSettings() {
    const selectedPort = document.getElementById("canPort").value;
    const selectedBitrate = document.getElementById("bitrate").value;

    try {
        const response = await fetch("/api/update_can_settings", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ serial_port: selectedPort, bitrate: selectedBitrate })
        });
        const data = await response.json();
        alert(data.message);
    } catch (error) {
        console.error("Error saving CAN settings:", error);
    }
}
