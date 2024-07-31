#!/bin/bash

# Start lightningd as a background process
lightningd --network=testnet --log-file /root/.lightning/testnet/lightning.log --daemon &&
sleep 5


# Start the Electrum daemon
electrum daemon --testnet -d 
sleep 5

# Run the Python script once
python3 /usr/src/app/probe.py

# Optional: You can add additional commands here if needed

# Keep the container running by tailing a log file or using a sleep loop
# For example, tail a log file (replace with your actual log file path)
tail -f /root/.lightning/testnet/lightning.log
