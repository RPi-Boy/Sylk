import time
import requests

def simulate_cloud_burst():
    print("Starting Cloud Burst Simulation (EC2 Tier)...")
    while True:
        # TODO: Logic to poll 'q_default' and 'charge' simulated cost
        print("Polling cloud queue...")
        time.sleep(10)

if __name__ == "__main__":
    simulate_cloud_burst()
