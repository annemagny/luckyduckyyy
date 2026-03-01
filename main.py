import serial
import time
from flask import Flask, jsonify, send_from_directory
# allow requests from file:// or other origins if you open the dashboard separately
try:
    from flask_cors import CORS
except ImportError:
    CORS = None

app = Flask(__name__)
if CORS:
    CORS(app)  # optional, avoids CORS errors when serving dashboard separately

# Configure serial connection
SERIAL_PORT = 'COM3'  # Change to your Arduino's COM port
BAUD_RATE = 9600
TIMEOUT = 1

# Initialize serial connection
try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=TIMEOUT)
    time.sleep(2)  # Wait for Arduino to initialize
except serial.SerialException as e:
    print(f"Error connecting to Arduino: {e}")
    ser = None

@app.route('/')
def index():
    """Serve the dashboard HTML so frontend can talk to the API."""
    # assumes index.html lives in the same directory as this script
    return send_from_directory('.', 'index.html')


@app.route('/water-level', methods=['GET'])
def get_water_level():
    """Fetch the current water level from Arduino"""    if ser is None or not ser.is_open:
        return jsonify({"error": "Arduino not connected"}), 500
    
    try:
        if ser.in_waiting > 0:
            line = ser.readline().decode('utf-8').strip()
            if "Water Level:" in line:
                value = line.split(": ")[1]
                return jsonify({"water_level": int(value)})
        return jsonify({"error": "No data available"}), 204
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/stream', methods=['GET'])
def stream_data():
    """Stream sensor data continuously"""
    def generate():
        while True:
            if ser and ser.is_open and ser.in_waiting > 0:
                line = ser.readline().decode('utf-8').strip()
                if "Water Level:" in line:
                    value = line.split(": ")[1]
                    yield f"data: {value}\n\n"
            time.sleep(0.5)
    
    return generate(), 200, {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache'
    }

if __name__ == '__main__':
    try:
        app.run(debug=True, port=5000)
    finally:
        if ser and ser.is_open:
            ser.close()