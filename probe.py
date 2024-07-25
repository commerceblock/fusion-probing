import sys
from pyln.client import LightningRpc, RpcError
import random
import string
import time
from datetime import datetime
import configparser
import psycopg2
from psycopg2 import sql
import json
import subprocess
import os
import requests

# Read configuration from the INI file
config = configparser.ConfigParser()
config.read('config.ini')

# Get the configuration values
db_credentials = {
    'dbname': config['database']['dbname'],
    'user': config['database']['user'],
    'password': config['database']['password'],
    'host': config['database']['host'],
    'port': config['database']['port']
}

network = config.get('settings', 'network', fallback='testnet')
rpc_path_mainnet = os.path.expanduser(config['lightning']['rpc_path_mainnet'])
rpc_path_testnet = os.path.expanduser(config['lightning']['rpc_path_testnet'])

if network == 'testnet':
    rpc_path = rpc_path_testnet
    print('Setting rpc to testnet path')
else:
    rpc_path = rpc_path_mainnet
    print("Setting rpc to mainnet path")

print('RPC Set was:', rpc_path)

table_name = config['table']['name']
print('Table name:', table_name)

# Environment/Configuration variables
run_full_probe = config.getboolean('settings', 'run_full_probe', fallback=False)
probing_value_msats = config.getint('settings', 'probing_value_msats', fallback=200000000)
probing_run_id = config['settings']['probing_run_id']
withdraw_now = config.get('settings', 'withdraw_now', fallback=False)
withdrawal_address = config.get('settings', 'withdrawal_address', fallback=None)

# Channel variables
channel_peer_id = config['channel']['peer_id']
channel_host = config['channel']['host']
channel_port = config['channel']['port']

print('Run full probe?:', run_full_probe)
print('Probing value:', probing_value_msats)
print('Probing run ID:', probing_run_id)
print('Channel node ID:', channel_peer_id)
print('Withdrawal address:', withdrawal_address)

# Electrum seed phrase
electrum_seed = config['wallet']['seed']
print('Electrum seed found:', electrum_seed)

# Add a check to see if /electrum/wallet exists, if it doesn't then make it
if not os.path.exists('/electrum/wallet/'):
    os.makedirs('/electrum/wallet/')

print('Loading electrum testnet wallet...')
# Recover Electrum wallet from seed
subprocess.run(['electrum', '--testnet', 'restore', electrum_seed], check=True)
print('Wallet loaded.')

print('Loading electrum testnet wallet...')
# Load the wallet
subprocess.run(['electrum', '--testnet', 'load_wallet',], check=True)
print('Electrum testnet wallet loaded..')

print('Getting info of the wallet...')
subprocess.run(['electrum', '--testnet', 'getinfo'], check=True)

print('Waiting for 60 seconds...')
time.sleep(60)
print('Checking wallet balance...')
# check how much is in the recovered wallet
recovered_balance = subprocess.run(['electrum', '--testnet', 'getbalance'], capture_output=True, text=True, check=True)
print('Recovered balance:', recovered_balance.stdout)

# recovered balance looks like this: { "confirmed": "1.06396422" }

# redo check balance to see if it's updated
print('Do we need to check the balance again? ...')
if 'confirmed' not in recovered_balance.stdout:
    print('Need to check for balance again...')
else:
    print('Dont need to check for balance again...')
# check if there is a confirmed value in the balance
while 'confirmed' not in recovered_balance.stdout:
    print('Balance is 0 or non existance. waiting 60 seconds to try again')
    time.sleep(60)
    recovered_balance = subprocess.run(['electrum', '--testnet', 'getbalance'], capture_output=True, text=True, check=True)
    print('Recovered balance:', recovered_balance.stdout)

'''
user_input = input("Continue? (y/n): ")
if user_input == 'n':
    print('Exiting script')
    exit()
elif user_input != 'y':
    print('Invalid input, exiting script')
    exit()
else:
    print('Continuing script')
'''

def get_this_node():
    try:
        result = subprocess.run(['lightning-cli', 'getinfo'], capture_output=True, text=True, check=True)
        node_info = json.loads(result.stdout)
        print('Found a node id:', node_info['id'])
        return node_info['id']
    except subprocess.CalledProcessError as e:
        print(f"Error: Unable to get node ID - {e}")
        return None

def connect_to_database():
    try:
        connection = psycopg2.connect(**db_credentials)
        return connection
    except Exception as e:
        print(f"Error: Unable to connect to the database - {e}")
        return None

def create_table(connection):
    try:
        cursor = connection.cursor()
        create_table_query = sql.SQL("""
            CREATE TABLE IF NOT EXISTS {} (
                id SERIAL PRIMARY KEY,
                dest VARCHAR,
                failcode VARCHAR,
                erring_node VARCHAR,
                erring_channel VARCHAR,
                route VARCHAR,
                time VARCHAR,
                amount VARCHAR
            )
        """).format(sql.Identifier(table_name))
        cursor.execute(create_table_query)
        connection.commit()
        print("Table created successfully")
    except Exception as e:
        print(f"Error: Unable to create table - {e}")

def insert_channel(connection, dest, failcode, erring_node, erring_channel, route, time, amount):
    values = (dest, failcode, erring_node, erring_channel, route, time, amount)
    try:
        cursor = connection.cursor()
        insert_query = sql.SQL("""
            INSERT INTO {} ({}, {}, {}, {}, {}, {}, {})
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """).format(sql.Identifier(table_name), sql.Identifier('dest'), sql.Identifier('failcode'),sql.Identifier('erring_node'),sql.Identifier('erring_channel'),sql.Identifier('route'),sql.Identifier('time'),sql.Identifier('amount'))
        cursor.execute(insert_query, values)
        connection.commit()
    except Exception as e:
        print(f"Error: Unable to insert JSON object - {e}")

def get_lightning_blockheight():
    try:
        result = subprocess.run(['lightning-cli', 'getinfo'], capture_output=True, text=True, check=True)
        node_info = json.loads(result.stdout)
        return node_info['blockheight']
    except subprocess.CalledProcessError as e:
        print(f"Error: Unable to get block height - {e}")
        return None

def get_latest_blockheight():
    network = config.get('settings', 'network', fallback='testnet')
    try:
        if network == 'testnet':
            response = requests.get('https://api.blockcypher.com/v1/btc/test3')
        else:
            response = requests.get('https://blockchain.info/latestblock')
        
        latest_block = response.json()
        
        # The response structure from BlockCypher is different for testnet
        if network == 'testnet':
            return latest_block['height']
        else:
            return latest_block['height']
    except Exception as e:
        print(f"Error: Unable to get latest block height - {e}")
        return None

def is_synchronized():
    lightning_blockheight = get_lightning_blockheight()
    latest_blockheight = get_latest_blockheight()

    if lightning_blockheight and latest_blockheight:
        print(f"Lightning block height: {lightning_blockheight}, Latest block height: {latest_blockheight}")
        return lightning_blockheight >= latest_blockheight - 1
    return False

print('Checking if lightningd is synchronized...')
while not is_synchronized():
    print('Not yet synchronized, waiting 30 seconds...')
    time.sleep(30)

print('lightningd is synchronized')


this_node = get_this_node()
print('This node:', this_node)

print('Connecting to database')
connection = connect_to_database()
    
if connection:
    print('Connected to database')
    print('Creating table')
    create_table(connection)


print('Trying to find LightningRPC at:', rpc_path)
l1 = LightningRpc(rpc_path)


print('l1 is equal to:', l1)
print('Trying to get list of nodes')
nodes = l1.listnodes()

print('Num Nodes: ' + str(len(nodes['nodes'])))

funds = l1.listfunds()
# connect to a initial node
print('Funds available:', funds)

# Generate a new payment address
paymentAddress = l1.newaddr()
print('Payment Address:', paymentAddress)

# Send payment to the new address
amount_btc = "0.001"  # specify the amount to send in BTC
subprocess.run(['electrum', 'payto', paymentAddress, amount_btc, '--wallet', '/electrum/wallet', '--testnet'], check=True)


print('Connecting to intial node')
# connect to a intial node
connect = l1.connect(channel_peer_id, channel_host, channel_port)
print('Connected to initial node')

peers = l1.listpeers()
print('List Peers:', peers)

print('Starting main loop')
total_nodes = 2701
counter = 0
if run_full_probe:
    print('Check if the node is funded...')
    if funds['channels'] == []:
        print('Node is not funded. Exiting...')
        sys.exit(1)
    else:
        print('Node is funded. Continuing...')
        print('Going through nodes...', len(nodes['nodes']))
        for node in nodes['nodes']:

            counter = counter + 1
            print('Counter:', counter)

            print(node['nodeid'])
            print()

            if node['nodeid'] == this_node:
                continue

            probe = {
                'destination': node['nodeid'],
                'started_at': str(datetime.now()),
                'node': node
            }

            found_route = True

            try:
                print('Trying to find route')
                probe['route'] = l1.getroute(node['nodeid'],probing_value_msats,1)['route']
                print('probe route value:', probe['route'])

            except RpcError as e:
                print('Failed to find route')
                print('Error was:', e)
                print('Error details:', e.error)
                print('Method that caused the error:', e.method)
                print('Payload sent to the method:', e.payload)
                found_route = False

            if found_route:
                print('Found route')
                rand_hash = ''.join(random.choice(string.hexdigits) for _ in range(64))

                print('rand_hash:', rand_hash)

                print()

                print('Sending payment')
                send = l1.sendpay(probe['route'],rand_hash)

                try:
                    print('Waiting for payment')
                    probe_r = l1.waitsendpay(rand_hash)
                except RpcError as e:
                    probe['finished_at'] = str(datetime.now())
                    probe['error'] = e.error['data']
                    probe['failcode'] = e.error['data']['failcode']

                print('probe:', probe)
                print('Route found, Sending to database')
                insert_channel(connection, probe['destination'], probe['error']['failcodename'], probe['error']['erring_node'],probe['error']['erring_channel'],json.dumps(probe['route']),probe['started_at'],100000000)
            else:
                print('No route found')
                insert_channel(connection, probe['destination'], "NO_ROUTE", "NONE", "NONE", "NONE", "NONE", "NONE")
elif withdraw_now == True:
    print('Withdrawing to the specified address:', withdrawal_address)
    try:
        result = subprocess.run(['lightning-cli', 'withdraw', withdrawal_address], capture_output=True, text=True, check=True)
        print('Withdrawal successful:', result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error: Unable to withdraw funds - {e}")
    print('script will wait here for 10000')
    time.sleep(10000)
else:
    print('Not running full probe')
    print('Waiting for manual intervention...')
    print('script will wait here for 10000')
    time.sleep(10000)

print('Finished -Closing connection')
connection.close()