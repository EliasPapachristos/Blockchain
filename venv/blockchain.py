import hashlib
import json
import requests

from time import time
from uuid import uuid4
from textwrap import dedent
from urllib.parse import urlparse
from flask import Flask, jsonify, request


class Blockchain(object):

    def __init__(self):

        self.chain = []
        self.nodes = set()
        self.current_transactions = []

        # This is Creating Our Genesis Block
        self.new_block(previous_hash=1, proof=100)

    """
    Add a New Node to the List of Nodes
    
        :param address: Address of the Node (e.g. 'http://192.168.0.9:5000'
    """

    def register_node(self, address):

        parsed_url = urlparse(address)

        if parsed_url.netlock:
            self.nodes.add(parsed_url.netlock)

        elif parsed_url.path:
            # Accepts an URL without scheme like '192.168.0.9:5000'.
            self.nodes.add(parsed_url.path)

        else:
            raise ValueError('Invalid URL')

    """
    Determine if the given Blockchain is Valid or Not
    
        :param chain: The blockchain
        :return True if it is Valid & False if it isn't
    """

    def valid_chain(self, chain):

        last_block = chain[0]
        current_index = 1

        while current_index < len(chain):

            block = chain[current_index]
            print(f'{last_block}')
            print(f'{block}')
            print("\n-----------\n")

            # Check if the Hash of the Block is Correct
            if block['previous_hash'] != self.hash(last_block):
                return False

            # Check if the PoW is Correct
            if not self.valid_proof(last_block['proof'], block['proof'], last_block['previous_hash']):
                return False

            last_block = block
            current_index += 1

        return True

    """
    Our Consensus Algorithm 
    In order to resolve the conflicts we are replacing
    our chain with the longest one of our network
    
        :return: True if our Chain was Replaced & False if not 
    """

    def resolve_conflicts(self):

        neighbours = self.nodes
        new_chain = None

        # Looking for chains longer than ours
        max_length = len(self.chain)

        # Take and verify the chains from all the nodes in our network
        for node in neighbours:
            response = requests.get(f'http://{node}/chain')

            if response.status_code == 200:
                length = response.json()['length']
                chain = response.json()['chain']

                # Check if the Chain has the Longer Length and if it is Valid
                if length > max_length and self.valid_chain(chain):
                    max_length = length
                    new_chain = chain

        # Replace our chain with the New, Valid & Longer Chain that we have discovered
        if new_chain:
            self.chain = new_chain
            return True

        return False

    """
    Create a new Block in the Blockchain
    
            :param proof: <int> The proof given by the Proof of Work algorithm
            :param previous_hash: (Optional) <str> Hash of previous Block
            :return: <dict> New Block
    """

    def new_block(self, proof, previous_hash=None):

        block = {
            'index': len(self.chain) + 1,
            'timestamp': time(),
            'transactions': self.current_transactions,
            'proof': proof,
            'previous_hash': previous_hash or self.hash(self.chain[-1])
        }

        # Reset the Current List of Transactions
        self.current_transactions = []

        self.chain.append(block)
        return block

    """
    Create a New Transaction to go into the Next Mined Block
    
        :param sender: <str> Address of the Sender (e.g. 231849sdf1654879fghj134679852fgh)
        :param recipient: <str> Address of the Sender (e.g. asaf12548765461vrb15495466rgdf)
        :param amount: <int> Amount (e.g. 7)
        :return: <int> The Index of the Block that will Hold this Transaction
    """

    def new_Transaction(self, sender, recipient, amount):

        self.current_transactions.append({
            'sender': sender,
            'recipient': recipient,
            'amount': amount
        })

        return self.last_block['index'] + 1

    @property
    def last_block(self):

        return self.chain[-1]

    """
    Create a SHA-256 Hash of a Block
    
        :param block: <dict> Block
        :return: <str>
    """

    # Check fot the Dictionary to be Ordered!
    @staticmethod
    def hash(block):

        block_string = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    """
    Simple Proof of Work Algorithm (PoW):
    
         - Find a number p' such that hash(pp') contains leading 4 zeroes, where p is the previous p'
         - p is the previous proof, and p' is the new proof
        :param last_proof: <int>
        :return: <int>
    """

    def proof_of_work(self, last_proof):

        last_proof = last_block['proof']
        last_hash = self.hash(last_block)

        proof = 0
        while self.valid_proof(last_proof, proof) is False:
            proof += 1

        return proof

    """
    Validates the Proof: We Check the Hash(last_proof, proof, last_hash) if it contain 4 leading zeroes
    
        :param last_proof: <int> Previous Proof
        :param proof: <int> Current Proof
        :param last_hash: <str> The Hash from the Previous Block
        :return: <bool> True if correct, False if not.
    """

    @staticmethod
    def valid_proof(last_proof, proof, last_hash):

        guess = f'{last_proof}{proof}{last_hash}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()
        return guess_hash[:4] == "0000"

    # Instance of Our Node
    app = Flask(__name__)

    # Generate a gloabaly Unique Address for this Node, Create a Random Name
    node_identifier = str(uuid4()).replace('-', '')

    # Instance of the Blockchain
    blockchain = Blockchain()

    # Create a /mine endpoint with a GET request
    @app.route('/mine', methods=['GET'])
    def mine():

        # We are Running the PoW algorith to GET the next proof
        last_block = blockchain.last_block
        proof = blockchain.proof_of_work(last_proof)

        # The sender is '0' in order to signify that this node has mined a New Coin
        # We Must recieve a Reward for finding the Proof
        blockchain.new_transaction(
            sender="0",
            recipient=node_identifier,
            amount=1
        )

        # Forge the New Block by Adding it to the Chain
        previous_hash = blockchain.hash(last_block)
        block = blockchain.new_block(proof, previous_hash)

        response = {
            'message': "A New Block is Forged!",
            'index': block['index'],
            'transactions': block['transactions'],
            'proof': block['proof'],
            'previous_hash': block['previous_hash']
        }

        return jsonify(response), 200

    # Create a /transaction/new endpoint with a POST request
    # We are Sending Data
    @app.route('/transactions/new', methods=['POST'])
    def new_transaction():

        values = request.get_json()

        # Check for the the Required data
        required = ['sender', 'recipient', 'amount']
        if not all(k in values for k in required):
            return 'Values are Missing telling you I am', 400

        # Create a new Transaction
        index = blockchain.new_transaction(values['sender'], values['recipient'], values['amount'])

        response = {'message': f'To the Block {index} this Transaction will be Added'}

        return jsonify(response), 201

    # Create a /chain endpoint with a GET request
    # We GET the Full Blockchain
    @app.route('/chain', methods=['GET'])
    def full_chain():

        response = {
            'chain': blockchain.chain,
            'length': len(blockchain.chain)
        }

        return jsonify(response), 200

    @app.route('/nodes/register', methods=['POST'])
    def register_nodes():

        values = request.get_json()

        nodes = values.get('nodes')

        if nodes is None:
            return "Error: At the Black Side you are. Supply a valid list of nodes you Must.", 400

        for node in nodes:
            blockchain.register_node(node)

        response = {
            'message': 'Added New Nodes Have Been',
            'total_nodes': list(blockchain.nodes),
        }

        return jsonify(response), 201

    @app.route('/nodes/resolve', methods=['GET'])
    def consensus():
        replaced = blockchain.resolve_conflicts()

        if replaced:
            response = {
                'message': 'Replaced Our chain was.',
                'new_chain': blockchain.chain
            }

        else:
            response = {
                'message': 'Our chain is reliable. May the Force be with our Chain!',
                'chain': blockchain.chain
            }

        return jsonify(response), 200

    # Run the Server on Port 5000
    if __name__ == '__main__':
        app.run(host='0.0.0.0', port=5000)
