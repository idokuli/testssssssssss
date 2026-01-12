from flask import Blueprint, request, render_template, jsonify
import subprocess
import multiprocessing
import os
import signal

stress_bp = Blueprint('stress', __name__)

# Global variable to track the process
stress_process = None

@stress_bp.route('/')
def stress_index():
    total_cores = multiprocessing.cpu_count()
    return render_template('stress.html', total_cores=total_cores)

@stress_bp.route('/run', methods=['POST'])
def run_stress():
    global stress_process
    cpus = request.form.get('cpu', '1')
    timeout = request.form.get('timeout', '30')
    
    # Start the process in the background
    stress_process = subprocess.Popen([
        "stress-ng", "--cpu", cpus, "--timeout", f"{timeout}s"
    ])
    return jsonify({"status": "started", "timeout": timeout})

@stress_bp.route('/cancel', methods=['POST'])
def cancel_stress():
    global stress_process
    if stress_process and stress_process.poll() is None:
        # Kill the process group
        stress_process.terminate()
        stress_process = None
        return jsonify({"status": "cancelled"})
    return jsonify({"status": "no_active_process"})