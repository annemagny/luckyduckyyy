# serial communication with Arduino (pyserial package)
# if package isn't installed we'll fall back to a stub so the server still runs
import sys

try:
    import serial
except ImportError:
    serial = None

import time
# the web framework may not be installed in the active interpreter; fail gracefully
try:
    from flask import Flask, jsonify, send_from_directory
except ImportError as e:
    print("\nERROR: Flask is not installed in the current Python environment.")
    print("Run `python -m pip install flask` or activate the correct virtualenv and try again.")
    print(f"(interpreter: {sys.executable})\n")
    raise

# allow requests from file:// or other origins if you open the dashboard separately
try:
    from flask_cors import CORS
except ImportError:
    CORS = None

app = Flask(__name__)
if CORS:
    CORS(app)  # optional, avoids CORS errors when serving dashboard separately

# Configure serial connection (won't work if pyserial isn't installed)
# default value can be overridden or detected automatically
SERIAL_PORT = 'COM7'  # Change to your Arduino's COM port
BAUD_RATE = 9600
TIMEOUT = 1

# helper to pick a port when user doesn't know which one is active
def pick_serial_port(preferred=None):
    # use the global `serial` module; it may be None if import failed
    if serial is None:
        return None

    # attempt to list ports; if the tools submodule is missing just bail
    try:
        ports = list(serial.tools.list_ports.comports())
    except Exception:
        return preferred

    if not ports:
        print("No serial ports found on this machine.")
        return None

    # show them for debugging
    print("Available serial ports:")
    for p in ports:
        print(f"  {p.device}: {p.description}")

    # try preferred first
    if preferred:
        for p in ports:
            if p.device == preferred:
                return preferred

    # otherwise pick the first one that mentions Arduino
    for p in ports:
        desc = p.description or ''
        if 'Arduino' in desc or 'CH340' in desc or 'CDC' in desc:
            print(f"Auto-selected port {p.device} based on description '{desc}'")
            return p.device

    # ultimately just return the first port
    return ports[0].device

# Initialize serial connection
ser = None
if serial is not None:
    port = pick_serial_port(SERIAL_PORT)
    if port and port != SERIAL_PORT:
        print(f"Using serial port {port} (preferred {SERIAL_PORT})")
    SERIAL_PORT = port
    if SERIAL_PORT:
        try:
            ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=TIMEOUT)
            time.sleep(2)  # Wait for Arduino to initialize
        except Exception as e:
            print(f"Error connecting to Arduino on {SERIAL_PORT}: {e}")
            ser = None
    else:
        print("No serial port could be opened; Arduino data will be unavailable.")
else:
    print("WARNING: pyserial not installed, running without Arduino data.")

@app.route('/')
def index():
    """Serve the dashboard HTML so frontend can talk to the API."""
    # assumes index.html lives in the same directory as this script
    return send_from_directory('.', 'index.html')


@app.route('/water-level', methods=['GET'])
def get_water_level():
    """Fetch the current water level from Arduino"""
    if ser is None or not ser.is_open:
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