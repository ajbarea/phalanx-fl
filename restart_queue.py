
import json
import subprocess
import sys
import time
from pathlib import Path
import psutil

# Configuration
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "out"

def get_queued_simulations():
    """Find all simulations with status='queued'."""
    queued_sims = []
    if not OUTPUT_DIR.exists():
        return []

    for sim_dir in OUTPUT_DIR.iterdir():
        if not sim_dir.is_dir():
            continue
        
        status_file = sim_dir / "status.json"
        config_file = sim_dir / "config.json"
        
        if status_file.exists() and config_file.exists():
            try:
                with open(status_file, 'r') as f:
                    status_data = json.load(f)
                
                # Check status
                if status_data.get('status') == 'queued':
                    # verify it's not actually running (PID check)
                    pid = status_data.get('pid')
                    if pid and psutil.pid_exists(pid):
                        print(f"Skipping {sim_dir.name}: Status is queued but PID {pid} is alive.")
                        continue
                    
                    queued_sims.append({
                        'id': sim_dir.name,
                        'path': sim_dir,
                        'config': config_file,
                        'created': status_data.get('updated_at', '')
                    })
            except Exception as e:
                print(f"Error reading {sim_dir.name}: {e}")
                
    # Sort by creation time to preserve order (roughly)
    queued_sims.sort(key=lambda x: x['created'])
    return queued_sims

def restart_queue():
    queued = get_queued_simulations()
    if not queued:
        print("No queued simulations found to restart.")
        return

    print(f"Found {len(queued)} queued simulations. Restarting...")
    
    for sim in queued:
        sim_id = sim['id']
        config_path = sim['config']
        
        print(f"Restarting {sim_id}...")
        
        # Construct command
        cmd = [
            sys.executable,
            "-m",
            "intellifl.simulation_runner",
            str(config_path)
        ]
        
        # Launch in background
        log_file = sim['path'] / "execution.log"
        status_file = sim['path'] / "status.json"
        
        with open(log_file, "a") as log:
            process = subprocess.Popen(
                cmd,
                cwd=BASE_DIR,
                stdout=log,
                stderr=subprocess.STDOUT,  # Merge stderr into stdout
            )
        
        # Update status.json to running + pid
        try:
            with open(status_file, "r+") as f:
                status_data = json.load(f)
                status_data["status"] = "running"
                status_data["pid"] = process.pid
                status_data["restarted_at"] = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())
                f.seek(0)
                json.dump(status_data, f, indent=2)
                f.truncate()
            print(f"  -> Started with PID {process.pid}")
        except Exception as e:
            print(f"  -> Warning: Failed to update status.json: {e}")
        
        time.sleep(1)  # Brief pause to allow process start
        
    print("All queued simulations have been relaunched.")

if __name__ == "__main__":
    restart_queue()
