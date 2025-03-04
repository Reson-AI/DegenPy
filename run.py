#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import subprocess
import signal
import threading
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Global variables for process management
processes = {}
stop_event = threading.Event()

def start_process(name, command, cwd=None):
    """Start a subprocess and return its process object"""
    print(f"Starting {name}...")
    
    if cwd:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
    else:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
    
    processes[name] = process
    
    # Start threads to read output
    threading.Thread(target=read_output, args=(process.stdout, f"{name} [OUT]"), daemon=True).start()
    threading.Thread(target=read_output, args=(process.stderr, f"{name} [ERR]"), daemon=True).start()
    
    return process

def read_output(pipe, prefix):
    """Read output from a pipe and print it with a prefix"""
    for line in pipe:
        print(f"{prefix}: {line.strip()}")

def stop_all_processes():
    """Stop all running processes"""
    print("Stopping all processes...")
    
    for name, process in processes.items():
        if process.poll() is None:  # Process is still running
            print(f"Terminating {name}...")
            process.terminate()
    
    # Wait for processes to terminate
    time.sleep(1)
    
    # Force kill any remaining processes
    for name, process in processes.items():
        if process.poll() is None:  # Process is still running
            print(f"Killing {name}...")
            process.kill()

def signal_handler(sig, frame):
    """Handle termination signals"""
    print(f"Received signal {sig}")
    stop_event.set()
    stop_all_processes()
    sys.exit(0)

def main():
    """Main function to start all components"""
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Create necessary directories
    os.makedirs("warehouse/txt_storage", exist_ok=True)
    
    try:
        # Start the data warehouse API
        warehouse_api = start_process(
            "warehouse_api",
            ["python", "api.py"],
            cwd="warehouse"
        )
        
        # Give the warehouse API time to start
        time.sleep(2)
        
        # Start the server API
        server_api = start_process(
            "server_api",
            ["python", "api.py"],
            cwd="server"
        )
        
        print("All services started. Press Ctrl+C to stop.")
        
        # Wait for processes to complete or for a termination signal
        while not stop_event.is_set():
            # Check if any process has terminated unexpectedly
            for name, process in list(processes.items()):
                if process.poll() is not None:
                    exit_code = process.returncode
                    print(f"{name} exited with code {exit_code}")
                    
                    if exit_code != 0:
                        print(f"Restarting {name}...")
                        if name == "warehouse_api":
                            start_process("warehouse_api", ["python", "api.py"], cwd="warehouse")
                        elif name == "server_api":
                            start_process("server_api", ["python", "api.py"], cwd="server")
                    
                    del processes[name]
            
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("Keyboard interrupt received")
    finally:
        stop_event.set()
        stop_all_processes()

if __name__ == "__main__":
    main()
