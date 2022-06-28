# -*- coding: utf-8 -*-
"""
Created on Wed Jan  8 19:26:32 2020
Last Update on Thur Apr  29 2021
@author: Jorge Castillo
@email: jacastillo8@outlook.com
"""

#FUTURE: RANDOMIZE PORTS OF CONTAINERS AND GENERATE FILE FOR PORTS
from .commands import Fabric, Caliper

import os, subprocess, json, yaml, ruamel.yaml, shutil, stat, warnings, time
from yaml import CLoader as Loader
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from ruamel.yaml.scalarstring import DoubleQuotedScalarString
from collections import OrderedDict

# Adjusting path variable for proper tree
reserved_dirs = ['blockchain', 'mqtt', 'emr']
path = os.getcwd()
path = path.replace('\\', '/')
replaced = 0
for reserved in reserved_dirs:
    if reserved == path.split('/')[-1]:
        path = path.replace('/' + reserved, '')
        replaced += 1
if replaced == 0:
    path += '/'
    
# Setting-up YAML representers
class literal_str(str): pass
class folded_str(str): pass

def dict_representer(dumper, data):
    return dumper.represent_dict(data.items())

def dict_constructor(loader, node):
    return OrderedDict(loader.construct_pairs(node))

def literal_representer(dumper, data):
    return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')

def folded_representer(dumper, data):
    return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='>')

# Loader
_mapping_tag = yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG
Loader.add_constructor(_mapping_tag, dict_constructor)

# Dumper
yaml.add_representer(OrderedDict, dict_representer)
yaml.add_representer(type(None), 
                       lambda dumper, value: dumper.represent_scalar(u'tag:yaml.org,2002:null', ''))
yaml.add_representer(literal_str, literal_representer)
yaml.add_representer(folded_str, folded_representer)

class ComposeFabric(object):

    def __init__(self, subpath, number_organizations, number_peers, org_users, 
                 channels, consortiums, consensus, block_form, domain_name, net_name, 
                 db, db_creds=[], arm64=False):
        if isinstance(net_name, list) and len(net_name) > 1:
            raise Exception("Argument 'net_name' must be singular.")
        elif isinstance(net_name, list):
            net_name = net_name[0]
        if not isinstance(number_peers, tuple):
            number_peers = tuple(number_peers for i in range(number_organizations))
        if not isinstance(org_users, tuple):
            org_users = tuple(org_users for i in range(number_organizations))
        if not isinstance(db_creds, list) or len(db_creds) > 2 or len(db_creds) == 1:
            raise Exception("Argument must be a list of length 2")
        self.path = path + '../blockchain_base/' + subpath
        # TODO - Enable definition of peers in Organization object (Node)
        self.numPeers = number_peers
        self.numOrgs = number_organizations
        self.numUsers = org_users
        self.numChannels = len(channels)
        self.nameChannels = channels
        self.consortiums = consortiums
        self.domain = domain_name
        self.netName = net_name
        self.consensus = consensus.lower()
        self.db = db.lower()
        self.db_creds = db_creds
        self.ports = {}
        self.arm64 = arm64
        self.block = { 'timeout': block_form[0], 'batch_size': { 'max_messages': block_form[1], 'max_bytes': block_form[2] }}
        self.fabric = Fabric(self.path, self.arm64)
        print(self.consortiums)

    def set_orderers(self, number_orderers):
        self.numOrds = number_orderers
        
    def create_env(self):
        with open('{}.env'.format(self.path), 'w+') as file:
            text = 'COMPOSE_PROJECT_NAME={}\nIMAGE_TAG=latest\nSYS_CHANNEL=net-sys-channel'.format(self.project_name)
            file.write(text)
    
    def create_ca_bash(self):
        text = '#!/bin/bash\n'
        for org in range(self.numOrgs):
            text += 'export NET_CA{0}_PRIVATE_KEY=$(cd crypto-config/peerOrganizations/org{0}.{1}/ca && ls *_sk)\n'.format(org + 1, self.domain)
        with open('{}scripts/ca_bash.sh'.format(self.path), 'w+') as file:
            file.write(text)
        # Update permissions for executable
        st = os.stat('{}scripts/ca_bash.sh'.format(self.path))
        os.chmod('{}scripts/ca_bash.sh'.format(self.path), st.st_mode | stat.S_IEXEC)

    def create_collections(self):
        normal_collection = {
            "name": "collectionNormal",
            "requiredPeerCount": 1,
            "maxPeerCount": 5,
            "blockToLive": 1000000,
            "memberOnlyRead": True
        }
        policy = 'OR('
        for o in range(self.numOrgs):
            policy += "'Org{}MSP.member'".format(o + 1)
            if o == (self.numOrgs - 1):
                break
            policy += ', '
        policy += ')'
        normal_collection['policy'] = policy
        collections = [normal_collection]
        for o in range(self.numOrgs):
            private_collection = {
                "name": "collectionPrivate{}".format(o + 1),
                "policy": "{}".format(policy), 
                "requiredPeerCount": 0,
                "maxPeerCount": 1,
                "blockToLive": 1000000,
                "memberOnlyRead": True
            }
            collections.append(private_collection)
        with open('{}scripts/collections.json'.format(self.path), 'w+') as file:
            json.dump(collections, file, indent=4)
            
    def create_compose_raft(self):
        doc = OrderedDict()
        doc['version'] = '2'
        doc['volumes'] = OrderedDict()
        doc['networks'] = OrderedDict()
        doc['networks'][self.netName] = None
        orderers = []
        start_number = 2 #changed
        for order in range(start_number, self.numOrds + start_number): 
            orderer = OrderedDict()
            orderer['container_name'] = 'orderer{}.{}'.format(order, self.domain)
            orderer['extends'] = OrderedDict()
            orderer['extends']['file'] = './base/peer-base.yaml'
            orderer['extends']['service'] = 'orderer-base'
            orderer['ports'] = [str(7050 + 1000*order) + ':' + str(7050)]
            self.ports['orderer{}.{}'.format(order, self.domain)] = (7050 + 1000*order)
            orderer['networks'] = [self.netName]
            orderer['volumes'] = ['./channel-artifacts/genesis.block:/var/hyperledger/orderer/orderer.genesis.block',
                                    './crypto-config/ordererOrganizations/{0}/orderers/orderer{1}.{0}/msp:/var/hyperledger/orderer/msp'.format(self.domain, order),
                                    './crypto-config/ordererOrganizations/{0}/orderers/orderer{1}.{0}/tls/:/var/hyperledger/orderer/tls'.format(self.domain, order),
                                    'orderer{}.{}:/var/hyperledger/production/orderer'.format(order, self.domain)]
            orderers.append(orderer)
            doc['volumes'][orderer['container_name']] = None
        doc['services'] = OrderedDict((c['container_name'],c) for c in orderers)
        with open('{}docker-compose-etcdraft2.yaml'.format(self.path), 'w') as file:
            yaml.dump(doc, file, default_flow_style=False)
        
    def create_compose_db(self, user='admin', password='adminpw'):
        doc = OrderedDict()
        doc['version'] = '2'
        doc['networks'] = OrderedDict() 
        doc['networks'][self.netName] = None
        peers = [c['container_name'] for c in self.peers]
        containers = []
        index = 0
        for org in range(self.numOrgs):
            for peer in range(self.numPeers[org]):
                # Database Dictionary
                db = OrderedDict()
                db['container_name'] = 'couchdb{}'.format(index)
                db['image'] = 'couchdb:3.1.1' #'hyperledger/fabric-couchdb'
                if self.arm64:
                    db['image'] = 'chinyati/fabric-couchdb:arm64-0.4.20'
                db['environment'] = ['COUCHDB_USER={}'.format(user),
                                      'COUCHDB_PASSWORD={}'.format(password)]
                db['ports'] = [str(5984 + 1000*index) + ':' + str(5984)]
                self.ports['couchdb{}'.format(index)] = (5984 + 1000*index)
                db['networks'] = [self.netName]
                containers.append(db)
                # Peer Dictionary
                Peer = OrderedDict()
                Peer['environment'] = ['CORE_LEDGER_STATE_STATEDATABASE=CouchDB',
                                        'CORE_LEDGER_STATE_COUCHDBCONFIG_COUCHDBADDRESS=couchdb{}:5984'.format(index),
                                        'CORE_LEDGER_STATE_COUCHDBCONFIG_USERNAME={}'.format(user),
                                        'CORE_LEDGER_STATE_COUCHDBCONFIG_PASSWORD={}'.format(password)]
                Peer['depends_on'] = ['couchdb{}'.format(index)]
                containers.append(Peer)
                index += 1
        doc['services'] = OrderedDict()
        index = 0
        for c in containers:
            try:
                doc['services'][c['container_name']] = c
            except:
                doc['services'][peers[index]] = c  
                index += 1
        with open('{}docker-compose-couch.yaml'.format(self.path), 'w') as file:
            yaml.dump(doc, file, default_flow_style=False)
    
    def create_compose_ca(self):
        doc = OrderedDict()
        doc['version'] = '2'
        doc['networks'] = OrderedDict()
        doc['networks'][self.netName] = None
        # Processing CAs
        cas = []
        for org in range(self.numOrgs):
            port = str(7054 + 1000*org)
            self.ports['ca.org{}.{}'.format(org + 1, self.domain)] = (7054 + 1000*org)
            ca = OrderedDict()
            ca['image'] = 'hyperledger/fabric-ca:1.5.2'
            if self.arm64:
                ca['image'] = 'chinyati/fabric-ca:arm64-1.4.8'
            ca['container_name'] = 'ca.org{}.{}'.format(org + 1, self.domain)
            ca['environment'] = ['FABRIC_CA_HOME=/etc/hyperledger/fabric-ca-server',
                                  'FABRIC_CA_SERVER_CA_NAME=ca-org{}'.format(org + 1),
                                  'FABRIC_CA_SERVER_TLS_ENABLED=true',
                                  'FABRIC_CA_SERVER_TLS_CERTFILE=/etc/hyperledger/fabric-ca-server-config/ca.org{}.{}-cert.pem'.format(org + 1, self.domain),
                                  'FABRIC_CA_SERVER_TLS_KEYFILE=/etc/hyperledger/fabric-ca-server-config/${NET_CA%d_PRIVATE_KEY}' % (org + 1),
                                  'FABRIC_CA_SERVER_PORT={}'.format(port)]
            ca['ports'] = [port + ':' + port]
            ca['command'] = folded_str("sh -c 'fabric-ca-server start --ca.certfile /etc/hyperledger/fabric-ca-server-config/ca.org%d.%s-cert.pem --ca.keyfile /etc/hyperledger/fabric-ca-server-config/${NET_CA%d_PRIVATE_KEY} -b admin:adminpw -d'" % (org + 1, self.domain, org + 1))
            ca['volumes'] = ['./crypto-config/peerOrganizations/org{}.{}/ca/:/etc/hyperledger/fabric-ca-server-config'.format(org + 1, self.domain)]
            ca['networks'] = [self.netName]
            cas.append(ca)
        doc['services'] = OrderedDict(('ca{}'.format(i), ca) for i,ca in zip(range(len(cas)), cas))
        with open('{}docker-compose-ca.yaml'.format(self.path), 'w') as file:
            yaml.dump(doc, file, default_flow_style=False)
        
    def create_base(self):
        doc = OrderedDict()
        doc['version'] = '2'
        doc['services'] = OrderedDict()
        # Peer Dictionary
        doc['services']['peer-base'] = OrderedDict()
        doc['services']['peer-base']['image'] = 'hyperledger/fabric-peer:2.3'
        if self.arm64:
            doc['services']['peer-base']['image'] = 'chinyati/fabric-peer:arm64-2.1.0'
        doc['services']['peer-base']['environment'] = ['CORE_VM_ENDPOINT=unix:///host/var/run/docker.sock',
                                                        'CORE_VM_DOCKER_HOSTCONFIG_NETWORKMODE=${COMPOSE_PROJECT_NAME}_%s' % self.netName,
                                                        'FABRIC_LOGGING_SPEC=INFO',
                                                        'CORE_PEER_TLS_ENABLED=true',
                                                        'CORE_PEER_GOSSIP_USELEADERELECTION=true',
                                                        'CORE_PEER_GOSSIP_ORGLEADER=false',
                                                        'CORE_PEER_PROFILE_ENABLED=true',
                                                        'CORE_PEER_TLS_CERT_FILE=/etc/hyperledger/fabric/tls/server.crt',
                                                        'CORE_PEER_TLS_KEY_FILE=/etc/hyperledger/fabric/tls/server.key',
                                                        'CORE_PEER_TLS_ROOTCERT_FILE=/etc/hyperledger/fabric/tls/ca.crt']
        doc['services']['peer-base']['working_dir'] = '/opt/gopath/src/github.com/hyperledger/fabric/peer'
        doc['services']['peer-base']['command'] = 'peer node start'
        # Orderer Dictionary
        doc['services']['orderer-base'] = OrderedDict()
        doc['services']['orderer-base']['image'] = 'hyperledger/fabric-orderer:2.3'
        if self.arm64:
            doc['services']['orderer-base']['image'] = 'chinyati/fabric-orderer:2.1'
        doc['services']['orderer-base']['environment'] = ['FABRIC_LOGGING_SPEC=INFO',
                                                           'ORDERER_GENERAL_LISTENADDRESS=0.0.0.0',
                                                           'ORDERER_GENERAL_GENESISMETHOD=file',
                                                           'ORDERER_GENERAL_GENESISFILE=/var/hyperledger/orderer/orderer.genesis.block',
                                                           'ORDERER_GENERAL_LOCALMSPID=OrdererMSP',
                                                           'ORDERER_GENERAL_LOCALMSPDIR=/var/hyperledger/orderer/msp',
                                                           'ORDERER_GENERAL_TLS_ENABLED=true',
                                                           'ORDERER_GENERAL_TLS_PRIVATEKEY=/var/hyperledger/orderer/tls/server.key',
                                                           'ORDERER_GENERAL_TLS_CERTIFICATE=/var/hyperledger/orderer/tls/server.crt',
                                                           'ORDERER_GENERAL_TLS_ROOTCAS=[/var/hyperledger/orderer/tls/ca.crt]',
                                                           'ORDERER_KAFKA_TOPIC_REPLICATIONFACTOR=1',
                                                           'ORDERER_KAFKA_VERBOSE=true',
                                                           'ORDERER_GENERAL_CLUSTER_CLIENTCERTIFICATE=/var/hyperledger/orderer/tls/server.crt',
                                                           'ORDERER_GENERAL_CLUSTER_CLIENTPRIVATEKEY=/var/hyperledger/orderer/tls/server.key',
                                                           'ORDERER_GENERAL_CLUSTER_ROOTCAS=[/var/hyperledger/orderer/tls/ca.crt]']
        doc['services']['orderer-base']['working_dir'] = '/opt/gopath/src/github.com/hyperledger/fabric'
        doc['services']['orderer-base']['command'] = 'orderer'
        with open('{}base/peer-base.yaml'.format(self.path), 'w') as file:
            yaml.dump(doc, file, default_flow_style=False)
    
    def create_compose_base(self, export=True):
        orderer_number = 1 #changed
        self.ports['orderer{}.{}'.format(orderer_number, self.domain)] = 7050 
        doc = OrderedDict()
        doc['version'] = '2'
        # Processing Orderer
        orderer = OrderedDict()
        orderer['container_name'] = 'orderer{}.{}'.format(orderer_number, self.domain) 
        orderer['extends'] = OrderedDict()
        orderer['extends']['file'] = 'peer-base.yaml'
        orderer['extends']['service'] = 'orderer-base'
        orderer['ports'] = ['7050:7050']
        orderer['volumes'] = ['../channel-artifacts/genesis.block:/var/hyperledger/orderer/orderer.genesis.block',
                                '../crypto-config/ordererOrganizations/{0}/orderers/orderer{1}.{0}/msp:/var/hyperledger/orderer/msp'.format(self.domain, orderer_number), 
                                '../crypto-config/ordererOrganizations/{0}/orderers/orderer{1}.{0}/tls:/var/hyperledger/orderer/tls'.format(self.domain, orderer_number),
                                'orderer{}.{}:/var/hyperledger/production/orderer'.format(orderer_number, self.domain)] 
        # Processing Peers by Organizations
        self.peers = []
        totalPeers = 0
        index = 0
        for org in range(self.numOrgs):
            for peer in range(self.numPeers[org]):
                port = 7051 + 1000*totalPeers
                self.ports['peer{}.org{}.{}'.format(peer, org + 1, self.domain)] = port
                Peer = OrderedDict()
                Peer['container_name'] = 'peer{}.org{}.{}'.format(peer, org + 1, self.domain)
                Peer['environment'] = ['CORE_PEER_ID=peer{}.org{}.{}'.format(peer, org + 1, self.domain),
                                         'CORE_PEER_ADDRESS=peer{}.org{}.{}:{}'.format(peer, org + 1, self.domain, port),
                                         'CORE_PEER_LISTENADDRESS=0.0.0.0:{}'.format(port),
                                         'CORE_PEER_CHAINCODEADDRESS=peer{}.org{}.{}:{}'.format(peer, org + 1, self.domain, port + 1),
                                         'CORE_PEER_CHAINCODELISTENADDRESS=0.0.0.0:{}'.format(port + 1),
                                         'CORE_PEER_GOSSIP_EXTERNALENDPOINT=peer{}.org{}.{}:{}'.format(peer, org + 1, self.domain, port),
                                         'CORE_PEER_LOCALMSPID=Org{}MSP'.format(org + 1)]
                #Peer['environment'].append('CORE_CHAINCODE_NODE_RUNTIME=hyperledger/fabric-nodeenv:2.3') # jacastillo8/fabric-nodeenv:amd
                Peer['environment'].append('CORE_CHAINCODE_EXECUTETIMEOUT=300s')
                Peer['environment'].append('CORE_VM_DOCKER_ATTACHSTDOUT=true')
                if self.arm64:
                    #Peer['environment'].append('CORE_CHAINCODE_BUILDER=chinyati/fabric-ccenv:$IMAGE_TAG')
                    Peer['environment'].append('CORE_CHAINCODE_NODE_RUNTIME=jacastillo8/fabric-nodeenv:arm')
                Peer['extends'] = OrderedDict()
                Peer['extends']['file'] = 'peer-base.yaml'
                Peer['extends']['service'] = 'peer-base'
                Peer['ports'] = [str(7051 + 1000*totalPeers) + ':' + str(7051 + 1000*totalPeers)]
                Peer['volumes'] = ['/var/run/:/host/var/run/',
                                     '../crypto-config/peerOrganizations/org{0}.{1}/peers/peer{2}.org{0}.{1}/msp:/etc/hyperledger/fabric/msp'.format(org + 1, self.domain, peer),
                                     '../crypto-config/peerOrganizations/org{0}.{1}/peers/peer{2}.org{0}.{1}/tls:/etc/hyperledger/fabric/tls'.format(org + 1, self.domain, peer),
                                     'peer{}.org{}.{}:/var/hyperledger/production'.format(peer, org + 1, self.domain)]
                self.peers.append(Peer)
                totalPeers += 1
            if self.numPeers[org] > 1:
                for peer in self.peers[index:]:
                    otherPeers = [p['environment'][1].split('=')[1] for p in self.peers[index:]]
                    otherPeers.remove(peer['environment'][1].split('=')[1])
                    peer['environment'].append('CORE_PEER_GOSSIP_BOOTSTRAP=' + ','.join(otherPeers))
            index += self.numPeers[org]
        doc['services'] = OrderedDict((c['container_name'],c) for c in [orderer] + self.peers)
        if export:
            with open('{}base/docker-compose-base.yaml'.format(self.path), 'w') as file:
                yaml.dump(doc, file, default_flow_style=False)
    
    def create_compose(self):
        doc = OrderedDict()
        doc['version'] = '2'
        doc['volumes'] = OrderedDict()
        doc['networks'] = OrderedDict()
        doc['networks'][self.netName] = None
        # Processing Orderer
        orderer = OrderedDict()
        orderer_number = 1 #changed
        orderer['container_name'] = 'orderer{}.{}'.format(orderer_number, self.domain) 
        orderer['extends'] = OrderedDict()
        orderer['extends']['file'] = 'base/docker-compose-base.yaml'
        orderer['extends']['service'] = 'orderer{}.{}'.format(orderer_number, self.domain) 
        orderer['container_name'] = 'orderer{}.{}'.format(orderer_number, self.domain) 
        orderer['networks'] = [self.netName] 
        # Processing Peers
        peers = []
        for org in range(self.numOrgs):
            for peer in range(self.numPeers[org]):
                Peer = OrderedDict()
                Peer['container_name'] = 'peer{}.org{}.{}'.format(peer, org + 1, self.domain)
                Peer['extends'] = OrderedDict()
                Peer['extends']['file'] = 'base/docker-compose-base.yaml'
                Peer['extends']['service'] = 'peer{}.org{}.{}'.format(peer, org + 1, self.domain)
                Peer['networks'] = [self.netName]
                peers.append(Peer)
        # Processing CLI
        cli = OrderedDict()
        cli['container_name'] = 'cli'
        cli['image'] = 'hyperledger/fabric-tools:2.3'
        if self.arm64:
            cli['image'] = 'chinyati/fabric-tools:arm64-2.1.0'
        cli['tty'] = True
        cli['stdin_open'] = True
        cli['environment'] = ['SYS_CHANNEL=$SYS_CHANNEL',
                               'GOPATH=/opt/gopath',
                               'CORE_VM_ENDPOINT=unix:///host/var/run/docker.sock',
                               'FABRIC_LOGGING_SPEC=INFO',
                               'CORE_PEER_ID=cli',
                               'CORE_PEER_ADDRESS=peer0.org1.{}:7051'.format(self.domain),
                               'CORE_PEER_LOCALMSPID=Org1MSP',
                               'CORE_PEER_TLS_ENABLED=true',
                               'CORE_PEER_TLS_CERT_FILE=/opt/gopath/src/github.com/hyperledger/fabric/peer/crypto/peerOrganizations/org1.{0}/peers/peer0.org1.{0}/tls/server.crt'.format(self.domain),
                               'CORE_PEER_TLS_KEY_FILE=/opt/gopath/src/github.com/hyperledger/fabric/peer/crypto/peerOrganizations/org1.{0}/peers/peer0.org1.{0}/tls/server.key'.format(self.domain),
                               'CORE_PEER_TLS_ROOTCERT_FILE=/opt/gopath/src/github.com/hyperledger/fabric/peer/crypto/peerOrganizations/org1.{0}/peers/peer0.org1.{0}/tls/ca.crt'.format(self.domain),
                               'CORE_PEER_MSPCONFIGPATH=/opt/gopath/src/github.com/hyperledger/fabric/peer/crypto/peerOrganizations/org1.{0}/users/Admin@org1.{0}/msp'.format(self.domain)]
        cli['working_dir'] = '/opt/gopath/src/github.com/hyperledger/fabric/peer'
        cli['command'] = '/bin/bash'
        cli['volumes'] = ['/var/run/:/host/var/run/',
                           './chaincode/:/opt/gopath/src/github.com/chaincode',
                           './crypto-config:/opt/gopath/src/github.com/hyperledger/fabric/peer/crypto/',
                           './scripts:/opt/gopath/src/github.com/hyperledger/fabric/peer/scripts/',
                           './channel-artifacts:/opt/gopath/src/github.com/hyperledger/fabric/peer/channel-artifacts']
        cli['depends_on'] = [orderer['container_name']] + [p['container_name'] for p in peers]
        cli['networks'] = [self.netName]
        for c in [orderer] + peers:
            doc['volumes'][c['container_name']] = None
        doc['services'] = OrderedDict((c['container_name'],c) for c in [orderer] + peers + [cli])
        with open('{}docker-compose.yaml'.format(self.path), 'w') as file:
            yaml.dump(doc, file, default_flow_style=False)
            
    def create_crypto(self):
        doc = OrderedDict()
        # Cryptographic artifacts for Orderers
        doc['OrdererOrgs'] = [OrderedDict()]
        doc['OrdererOrgs'][0]['Name'] = 'Orderer'
        doc['OrdererOrgs'][0]['Domain'] = self.domain
        doc['OrdererOrgs'][0]['EnableNodeOUs'] = True
        doc['OrdererOrgs'][0]['Specs'] = []
        start_number = 1 # changed
        for order in range(start_number, self.numOrds + 1 + start_number):
            hostname = OrderedDict()
            if order == 0:
                hostname['Hostname'] = 'orderer'
            else:
                hostname['Hostname'] = 'orderer{}'.format(order)
            doc['OrdererOrgs'][0]['Specs'].append(hostname)
        # Cryptographic artifacts for Peers and Users
        doc['PeerOrgs'] = []
        for org in range(self.numOrgs):
            peerOrg = OrderedDict()
            peerOrg['Name'] = 'Org{}'.format(org + 1)
            peerOrg['Domain'] = 'org{}.{}'.format(org + 1, self.domain)
            peerOrg['EnableNodeOUs'] = True
            peerOrg['Template'] = OrderedDict()
            peerOrg['Template']['Count'] = self.numPeers[org]
            peerOrg['Users'] = OrderedDict()
            peerOrg['Users']['Count'] = self.numUsers[org]
            doc['PeerOrgs'].append(peerOrg)
        with open('{}crypto-config.yaml'.format(self.path), 'w') as file:
            yaml.dump(doc, file, default_flow_style=False)
            
    def create_ccp(self):
        for org in range(self.numOrgs):
            doc = OrderedDict()
            doc['name'] = '{}-network-org{}'.format(self.netName, org + 1)
            doc['version'] = '1.0.0'
            doc['client'] = OrderedDict()
            doc['client']['organization'] = 'Org{}'.format(org + 1)
            doc['client']['connection'] = OrderedDict()
            doc['client']['connection']['timeout'] = OrderedDict()
            doc['client']['connection']['timeout']['peer'] = OrderedDict()
            doc['client']['connection']['timeout']['peer']['endorser'] = 300
            doc['client']['connection']['timeout']['peer']['eventHub'] = 300
            doc['client']['connection']['timeout']['orderer'] = 30
            doc['organizations'] = OrderedDict()
            doc['organizations']['Org{}'.format(org + 1)] = OrderedDict()
            doc['organizations']['Org{}'.format(org + 1)]['mspid'] = 'Org{}MSP'.format(org + 1)
            doc['organizations']['Org{}'.format(org + 1)]['peers'] = ['peer{}.org{}.{}'.format(p, org + 1, self.domain) for p in range(self.numPeers[org])]
            doc['organizations']['Org{}'.format(org + 1)]['certificateAuthorities'] = ['ca.org{}.{}'.format(org + 1, self.domain)]
            doc['peers'] = OrderedDict()
            for peer in range(self.numPeers[org]):
                with open('{2}crypto-config/peerOrganizations/org{0}.{1}/tlsca/tlsca.org{0}.{1}-cert.pem'.format(org + 1, self.domain, self.path)) as file:
                    pem = ''
                    for line in file:
                        pem += line
                doc['peers']['peer{}.org{}.{}'.format(peer, org + 1, self.domain)] = OrderedDict()
                doc['peers']['peer{}.org{}.{}'.format(peer, org + 1, self.domain)]['url'] = 'grpcs://localhost:{}'.format(self.ports['peer{}.org{}.{}'.format(peer, org + 1, self.domain)])
                doc['peers']['peer{}.org{}.{}'.format(peer, org + 1, self.domain)]['tlsCACerts'] = OrderedDict()
                doc['peers']['peer{}.org{}.{}'.format(peer, org + 1, self.domain)]['tlsCACerts']['pem'] = literal_str(pem)
                doc['peers']['peer{}.org{}.{}'.format(peer, org + 1, self.domain)]['grpcOptions'] = OrderedDict()
                doc['peers']['peer{}.org{}.{}'.format(peer, org + 1, self.domain)]['grpcOptions']['ssl-target-name-override'] = 'peer{}.org{}.{}'.format(peer, org + 1, self.domain)
                doc['peers']['peer{}.org{}.{}'.format(peer, org + 1, self.domain)]['grpcOptions']['hostnameOverride'] = 'peer{}.org{}.{}'.format(peer, org + 1, self.domain)
            with open('{2}crypto-config/peerOrganizations/org{0}.{1}/ca/ca.org{0}.{1}-cert.pem'.format(org + 1, self.domain, self.path)) as file:
                pem = ''
                for line in file:
                    pem += line
            doc['certificateAuthorities'] = OrderedDict()
            doc['certificateAuthorities']['ca.org{}.{}'.format(org + 1, self.domain)] = OrderedDict()
            doc['certificateAuthorities']['ca.org{}.{}'.format(org + 1, self.domain)]['url'] = 'https://localhost:{}'.format(self.ports['ca.org{}.{}'.format(org + 1, self.domain)])
            doc['certificateAuthorities']['ca.org{}.{}'.format(org + 1, self.domain)]['caName'] = 'ca-org{}'.format(org + 1)
            doc['certificateAuthorities']['ca.org{}.{}'.format(org + 1, self.domain)]['tlsCACerts'] = OrderedDict()
            doc['certificateAuthorities']['ca.org{}.{}'.format(org + 1, self.domain)]['tlsCACerts']['pem'] = literal_str(pem)
            doc['certificateAuthorities']['ca.org{}.{}'.format(org + 1, self.domain)]['httpOptions'] = OrderedDict()
            doc['certificateAuthorities']['ca.org{}.{}'.format(org + 1, self.domain)]['httpOptions']['verify'] = False
            # Store Dictionaries in both JSON and YAML format
            with open('{}connection-org{}.json'.format(self.path, org + 1), 'w') as file:
                json.dump(doc, file, indent=4)
            with open('{}connection-org{}.yaml'.format(self.path, org + 1), 'w') as file:
                yaml.dump(doc, file, default_flow_style=False)
        
    def create_configtx(self, anchors=1):
        if anchors < 1:
            Exception("Number of Anchor Peers must be at least 1 per organization.")
        ryaml = ruamel.yaml.YAML()
        ryaml.default_style = ""
        # Members for Policy definition
        members = ['Readers', 'Writers', 'Admins']
        doc = CommentedMap()
        # Policy set-up for Orderer
        ordererOrg = CommentedMap()
        ordererOrg.yaml_set_anchor('OrdererOrg', True)
        ordererOrg['Name'] = 'OrdererOrg'
        ordererOrg['ID'] = 'OrdererMSP'
        ordererOrg['MSPDir'] = 'crypto-config/ordererOrganizations/{}/msp'.format(self.domain)
        ordererOrg['Policies'] = CommentedMap()
        # Rules defined for specific Policy
        rules = ['member', 'member', 'admin']
        for member, rule in zip(members, rules):
            ordererOrg['Policies'][member] = CommentedMap()
            ordererOrg['Policies'][member]['Type'] = 'Signature'
            ordererOrg['Policies'][member]['Rule'] = DoubleQuotedScalarString("OR('OrdererMSP.{}')".format(rule))
        # Policy set-up for Organizations
        orgs = []
        for org in range(self.numOrgs):
            Org = CommentedMap()
            Org.yaml_set_anchor('Org{}'.format(org + 1), True)
            Org['Name'] = 'Org{}MSP'.format(org + 1)
            Org['ID'] = 'Org{}MSP'.format(org + 1)
            Org['MSPDir'] = 'crypto-config/peerOrganizations/org{}.{}/msp'.format(org + 1, self.domain)
            Org['Policies'] = CommentedMap()
            # Rules defined for specific Policy
            rules = ['admin', 'client', 'peer']
            for member, i in zip(members, range(len(rules))):
                Org['Policies'][member] = CommentedMap()
                Org['Policies'][member]['Type'] = 'Signature'
                Org['Policies'][member]['Rule'] = DoubleQuotedScalarString("OR" + str(tuple('Org{}MSP.'.format(org + 1) + 
                   rule for rule in rules[:len(rules) - i]))) 
            # Remove last comma of single element tuple
            Org['Policies'][member]['Rule']= Org['Policies'][member]['Rule'].replace(',', '')
            # Anchor Peers set up
            anchorPeers = []
            for anchor in range(anchors):
                anchorPeer = CommentedMap()
                anchorPeer['Host'] = 'peer{}.org{}.{}'.format(anchor, org + 1, self.domain)
                anchorPeer['Port'] = self.ports['peer{}.org{}.{}'.format(anchor, org + 1, self.domain)]
                anchorPeers.append(anchorPeer)
            Org['AnchorPeers'] = CommentedSeq(anchorPeers) #[anchor for anchor in anchorPeers]
            orgs.append(Org)
        doc['Organizations'] = CommentedSeq([ordererOrg] + orgs)
        # Version set-up Channel
        doc['Capabilities'] = CommentedMap()
        doc['Capabilities']['Channel'] = CommentedMap()
        doc['Capabilities']['Channel'].yaml_set_anchor('ChannelCapabilities', True)
        doc['Capabilities']['Channel']['V1_4_3'] = True
        doc['Capabilities']['Channel']['V1_3'] = False
        doc['Capabilities']['Channel']['V1_1'] = False
        # Version set-up Orderer
        doc['Capabilities']['Orderer'] = CommentedMap()
        doc['Capabilities']['Orderer'].yaml_set_anchor('OrdererCapabilities', True)
        doc['Capabilities']['Orderer']['V1_4_2'] = True
        doc['Capabilities']['Orderer']['V1_1'] = False
        # Version set-up Application
        doc['Capabilities']['Application'] = CommentedMap()
        doc['Capabilities']['Application'].yaml_set_anchor('ApplicationCapabilities', True)
        doc['Capabilities']['Application']['V1_4_2'] = True
        doc['Capabilities']['Application']['V1_3'] = False
        doc['Capabilities']['Application']['V1_2'] = False
        doc['Capabilities']['Application']['V1_1'] = False        
        # Policy set-up for application
        doc['Application'] = CommentedMap()
        doc['Application'].yaml_set_anchor('ApplicationDefaults', True)
        doc['Application']['Organizations'] = None
        doc['Application']['Policies'] = CommentedMap()
        # Rules defined for specific Policy
        rules = ['ANY', 'ANY', 'MAJORITY']
        for member, rule in zip(members, rules):
            doc['Application']['Policies'][member] = CommentedMap()
            doc['Application']['Policies'][member]['Type'] = 'ImplicitMeta'
            doc['Application']['Policies'][member]['Rule'] = DoubleQuotedScalarString('{} {}'.format(rule, member)) 
        # Using alias for Application Capabilities
        doc['Application']['Capabilities'] = CommentedMap()
        doc['Application']['Capabilities'].add_yaml_merge([(0, doc['Capabilities']['Application'])])
        # Orderer Default settings
        doc['Orderer'] = CommentedMap()
        doc['Orderer'].yaml_set_anchor('OrdererDefaults', True)
        doc['Orderer']['OrdererType'] = 'solo'
        #doc['Orderer']['Addresses'] = ['orderer1.{}:{}'.format(self.domain, self.ports['orderer1.{}'.format(self.domain)])] #changed
        doc['Orderer']['BatchTimeout'] = self.block['timeout']
        doc['Orderer']['BatchSize'] = CommentedMap()
        doc['Orderer']['BatchSize']['MaxMessageCount'] = self.block['batch_size']['max_messages']
        doc['Orderer']['BatchSize']['AbsoluteMaxBytes'] = '99 MB'
        doc['Orderer']['BatchSize']['PreferredMaxBytes'] = self.block['batch_size']['max_bytes']
        # Used if Kafka is implemented
        doc['Orderer']['Kafka'] = CommentedMap()
        doc['Orderer']['Kafka']['Brokers'] = ['127.0.0.1:9092']     # Modify after adding Kafka into Class
        doc['Orderer']['Organizations'] = None
        doc['Orderer']['Policies'] = CommentedMap()
        # Policy set-up for Orderer
        rules = ['ANY', 'ANY', 'MAJORITY', 'ANY']
        for member, rule in zip(members + ['BlockValidation'], rules):
            doc['Orderer']['Policies'][member] = CommentedMap()
            doc['Orderer']['Policies'][member]['Type'] = 'ImplicitMeta'
            if member == 'BlockValidation':
                doc['Orderer']['Policies'][member]['Rule'] = DoubleQuotedScalarString('{} {}'.format(rule, 'Writers'))
            else:
                doc['Orderer']['Policies'][member]['Rule'] = DoubleQuotedScalarString('{} {}'.format(rule, member)) 
        # Policy set-up for Channel
        doc['Channel'] = CommentedMap()
        doc['Channel'].yaml_set_anchor('ChannelDefaults', True)
        doc['Channel']['Policies'] = CommentedMap()
        rules = ['ANY', 'ANY', 'MAJORITY']
        for member, rule in zip(members, rules):
            doc['Channel']['Policies'][member] = CommentedMap()
            doc['Channel']['Policies'][member]['Type'] = 'ImplicitMeta'
            doc['Channel']['Policies'][member]['Rule'] = DoubleQuotedScalarString('{} {}'.format(rule, member)) 
        # Using alias for Channel Capabilities
        doc['Channel']['Capabilities'] = CommentedMap()
        doc['Channel']['Capabilities'].add_yaml_merge([(0, doc['Capabilities']['Channel'])])
        # Profile definition
        doc['Profiles'] = CommentedMap()
        doc['Profiles']['EtcdRaft'] = CommentedMap()
        doc['Profiles']['EtcdRaft'].add_yaml_merge([(0, doc['Channel'])])
        doc['Profiles']['EtcdRaft']['Capabilities'] = CommentedMap()
        doc['Profiles']['EtcdRaft']['Capabilities'].add_yaml_merge([(0, doc['Capabilities']['Channel'])])
        doc['Profiles']['EtcdRaft']['Orderer'] = CommentedMap()
        doc['Profiles']['EtcdRaft']['Orderer'].add_yaml_merge([(0, doc['Orderer'])])
        doc['Profiles']['EtcdRaft']['Orderer']['OrdererType'] = 'etcdraft'
        doc['Profiles']['EtcdRaft']['Orderer']['EtcdRaft'] = CommentedMap()
        consenters = []
        start_number = 1 #changed
        for orderer in range(start_number, self.numOrds + 1 + start_number):
            consenter = CommentedMap()
            if orderer == 0:
                consenter['Host'] = 'orderer{}.{}'.format('', self.domain)
                consenter['Port'] = self.ports['orderer.{}'.format(self.domain)]
                consenter['ClientTLSCert'] = 'crypto-config/ordererOrganizations/{0}/orderers/orderer{1}.{0}/tls/server.crt'.format(self.domain, '')
                consenter['ServerTLSCert'] = 'crypto-config/ordererOrganizations/{0}/orderers/orderer{1}.{0}/tls/server.crt'.format(self.domain, '')
            else:
                consenter['Host'] = 'orderer{}.{}'.format(orderer, self.domain)
                consenter['Port'] = self.ports['orderer1.{}'.format(self.domain)] # changed
                consenter['ClientTLSCert'] = 'crypto-config/ordererOrganizations/{0}/orderers/orderer{1}.{0}/tls/server.crt'.format(self.domain, orderer)
                consenter['ServerTLSCert'] = 'crypto-config/ordererOrganizations/{0}/orderers/orderer{1}.{0}/tls/server.crt'.format(self.domain, orderer)
            consenters.append(consenter)
        doc['Profiles']['EtcdRaft']['Orderer']['EtcdRaft']['Consenters'] = CommentedSeq()
        doc['Profiles']['EtcdRaft']['Orderer']['EtcdRaft']['Consenters'].extend(consenters)
        if start_number == 0:
            doc['Orderer']['Addresses'] = ['orderer.{}:{}'.format(self.domain, self.ports['orderer.{}'.format(self.domain)])]
            doc['Profiles']['EtcdRaft']['Orderer']['Addresses'] = CommentedSeq(['{}:{}'.format(c['Host'], self.ports['orderer{}.{}'.format('', self.domain)]) for c in consenters])
        else:
            doc['Orderer']['Addresses'] = ['orderer{}.{}:{}'.format(start_number, self.domain, self.ports['orderer{}.{}'.format(start_number, self.domain)])]
            doc['Profiles']['EtcdRaft']['Orderer']['Addresses'] = CommentedSeq(['{}:{}'.format(c['Host'], self.ports['orderer{}.{}'.format(start_number, self.domain)]) for c in consenters])
        doc['Profiles']['EtcdRaft']['Orderer']['Organizations'] = CommentedSeq()
        doc['Profiles']['EtcdRaft']['Orderer']['Organizations'].extend([doc['Organizations'][0]])
        doc['Profiles']['EtcdRaft']['Orderer']['Capabilities'] = CommentedMap()
        doc['Profiles']['EtcdRaft']['Orderer']['Capabilities'].add_yaml_merge([(3, doc['Capabilities']['Orderer'])])
        doc['Profiles']['EtcdRaft']['Application'] = CommentedMap()
        doc['Profiles']['EtcdRaft']['Application'].add_yaml_merge([(0, doc['Application'])])
        doc['Profiles']['EtcdRaft']['Application']['Organizations'] = [CommentedMap()]
        doc['Profiles']['EtcdRaft']['Application']['Organizations'][0].add_yaml_merge([(0, doc['Organizations'][0])])
        doc['Profiles']['EtcdRaft']['Consortiums'] = CommentedMap()
        for c in range(len(self.consortiums)):
            doc['Profiles']['EtcdRaft']['Consortiums']['Consortium{}'.format(c+1)] = CommentedMap()
            doc['Profiles']['EtcdRaft']['Consortiums']['Consortium{}'.format(c+1)]['Organizations'] = CommentedSeq()
            orgs = [doc['Organizations'][o] for o in self.consortiums[c]]
            doc['Profiles']['EtcdRaft']['Consortiums']['Consortium{}'.format(c+1)]['Organizations'].extend(orgs)   
        for c in range(self.numChannels):
            doc['Profiles']['Channel{}'.format(c+1)] = CommentedMap()
            doc['Profiles']['Channel{}'.format(c+1)]['Consortium'] = 'Consortium{}'.format(c+1)
            doc['Profiles']['Channel{}'.format(c+1)].add_yaml_merge([(1, doc['Channel'])])
            doc['Profiles']['Channel{}'.format(c+1)]['Application'] = CommentedMap()
            doc['Profiles']['Channel{}'.format(c+1)]['Application'].add_yaml_merge([(0, doc['Application'])])
            doc['Profiles']['Channel{}'.format(c+1)]['Application']['Organizations'] = CommentedSeq()
            orgs = [doc['Organizations'][o] for o in self.consortiums[c]]
            doc['Profiles']['Channel{}'.format(c+1)]['Application']['Organizations'].extend(orgs)
            doc['Profiles']['Channel{}'.format(c+1)]['Application']['Capabilities'] = CommentedMap()
            doc['Profiles']['Channel{}'.format(c+1)]['Application']['Capabilities'].add_yaml_merge([(0, doc['Capabilities']['Application'])])
        with open('{}configtx.yaml'.format(self.path),'w') as file:
            ryaml.dump(doc, file)
    
    def create_fabric(self, project_name='net', orderers=4):
        self.project_name = project_name
        # Removing unnecessary directories
        if os.path.exists("{}/config".format(self.path)) and os.path.isdir("{}/config".format(self.path)):
            shutil.rmtree("{}/config".format(self.path))
        print("[*] Files will be generated in '%s'" % self.path)
        print("[+] Generating base files in './base'...", end='')
        # Creates base files
        self.create_base()
        self.create_compose_base()
        print('DONE')
        print("[+] Generating compose files...", end='')
        # Creates docker-compose file
        self.create_compose()
        self.set_orderers(orderers) # original 4
        # Creates compose-raft file
        self.create_compose_raft()
        if self.db == 'couchdb':
            if not self.db_creds:
                self.db_creds = ['' for i in range(2)]
            # Creates DB file
            #self.create_compose_db(user=self.db_creds[0], password=self.db_creds[1])
            self.create_compose_db()
        # Creates CA file
        self.create_compose_ca()
        print('DONE')
        # Exports file containing port map
        #print("[+] Exporting 'container-port' mapping into JSON...", end='')
        #with open('{}scripts/port_map.json'.format(self.path), 'w+') as file:
        #    json.dump(self.ports, file, indent=4)
        #print("DONE")
        print("[+] Generating certificate config files...", end='')
        # Creates crypto-config
        self.create_crypto()
        # Use cryptogen to generate all certificates
        print('DONE')
        self.fabric.newCryptoMaterial()
        print("[+] Generating environmental variable file...", end='')
        # Creates .env 
        self.create_env()
        print("DONE")
        print("[+] Generating CCP files...", end='')
        # Creates CCP Files
        self.create_ccp()
        print('DONE')
        print("[+] Generating channel configuration profiles...", end='')
        self.create_configtx()
        print("DONE") 
        print("[+] Generating collections file...", end="")
        self.create_collections()
        print("DONE\n")

    # TODO - Fix me
    def create_channel_artifact(self, channel_profile, channe_name):
        # TODO - add way to modify/recreate configtx yaml file
        self.fabric.newChannelConfiguration(channel_profile, channe_name)
        # TODO - create channel and make peers join 

    def build_fabric(self, project_name='net', orderers=4):
        self.create_fabric(project_name, orderers)
        self.fabric.newGenesisBlock()
        for i, c in enumerate(self.nameChannels):
            self.fabric.newChannelConfiguration('Channel{}'.format(i+1), c)
            self.fabric.newAnchorUpdate('Channel{}'.format(i+1), self.consortiums[i], c)
        self.fabric.instantiateNetwork(self.numOrgs, self.domain)
        time.sleep(5)
        for i, channel in enumerate(self.nameChannels):
            org = self.consortiums[i][0]
            self.fabric.createChannel(org, self.domain, self.ports, 'Channel{}'.format(i+1), channel)
        for i, channel in enumerate(self.nameChannels):
            orgs = self.consortiums[i]
            for j, o in enumerate(orgs):
                for p in range(self.numPeers[j]):
                    self.fabric.joinChannel(p, o, self.domain, self.ports, channel)
        for i, channel in enumerate(self.nameChannels):
            orgs = self.consortiums[i]
            for o in orgs:
                self.fabric.updateAnchorPeers(0, o, self.domain, self.ports, channel)
    
    def install_contract(self, name, version, org=None):
        self.create_compose_base(False)
        if org is None:
            for i, o in enumerate(self.consortiums[0]):
                for p in range(self.numPeers[i]):
                    self.fabric.installContract(p, o, self.domain, self.ports, name, version)
            self.fabric.instantiateContract(self.consortiums[0][0], self.domain, self.ports,
                                            name, version, self.nameChannels[0])
        else:
            o = int(org)
            i = o - 1
            for p in range(self.numPeers[i]):
                self.fabric.installContract(p, o, self.domain, self.ports, name, version)
            self.fabric.instantiateContract(o, self.domain, self.ports, name, version, 
                                            self.nameChannels[0])

        
        
class ComposeCaliper(object):
    def __init__(self, number_organizations, number_peers, number_orderers, 
                 channel, consortium, domain_name, contracts):
        self.path = path +'../blockchain_base'
        self.numOrgs = number_organizations
        self.numPeers = number_peers
        self.numOrds = number_orderers
        self.channel = { 'name': channel[0], 'consortium_name': 'Consortium{}'.format(channel[1]) }
        self.consortium = consortium
        self.domain = domain_name
        self.contracts = contracts
        self.project_name = 'test_benchmark'
        self.caliper = Caliper(self.path)

    def create_compose_caliper(self):
        doc = OrderedDict()
        doc['version'] = '2'
        doc['services'] = OrderedDict()
        doc['services']['caliper'] = OrderedDict()
        doc['services']['caliper']['container_name'] = 'caliper'
        doc['services']['caliper']['image'] = 'hyperledger/caliper:0.3.0'
        doc['services']['caliper']['command'] = 'launch master'
        doc['services']['caliper']['environment'] = ['CALIPER_BIND_SUT=fabric:1.4.4',
                                                     'CALIPER_BENCHCONFIG=benchmarks/{}/config.yaml'.format(self.project_name),
                                                     'CALIPER_NETWORKCONFIG=benchmarks/{}/caliper_network.yaml'.format(self.project_name)]
        doc['services']['caliper']['volumes'] = ['./:/hyperledger/caliper/workspace']
        doc['services']['caliper']['network_mode'] = 'host'
        with open('{}/docker-compose-caliper.yaml'.format(self.path), 'w') as file:
            yaml.dump(doc, file, default_flow_style=False)

    def create_network_file(self):
        doc = OrderedDict()
        doc['name'] = 'Fabric'
        doc['version'] = '1.0'
        doc['mutual-tls'] = False
        doc['caliper'] = OrderedDict()
        doc['caliper']['blockchain'] = 'fabric'
        doc['info'] = OrderedDict()
        doc['info']['Version'] = '1.4.4'
        doc['info']['Size'] = '{} Orgs with {} Peers'.format(self.numOrgs, self.numPeers)
        doc['info']['Orderer'] = 'Raft'
        doc['info']['Distribution'] = 'Single Host'
        doc['info']['StateDB'] = 'CouchDB'
        doc['clients'] = OrderedDict()
        for c in range(self.numOrgs):
            doc['clients']['client0.org{}.{}'.format(c+1, self.domain)] = OrderedDict()
            doc['clients']['client0.org{}.{}'.format(c+1, self.domain)]['client'] = OrderedDict()
            doc['clients']['client0.org{}.{}'.format(c+1, self.domain)]['client']['organization'] = 'Org{}'.format(c+1)
            doc['clients']['client0.org{}.{}'.format(c+1, self.domain)]['client']['credentialStore'] = OrderedDict()
            doc['clients']['client0.org{}.{}'.format(c+1, self.domain)]['client']['credentialStore']['path'] = '/tmp/hfc-kvs/org{}'.format(c+1)
            doc['clients']['client0.org{}.{}'.format(c+1, self.domain)]['client']['credentialStore']['cryptoStore'] = OrderedDict()
            doc['clients']['client0.org{}.{}'.format(c+1, self.domain)]['client']['credentialStore']['cryptoStore']['path'] = '/tmp/hfc-cvs/org{}'.format(c+1)
            doc['clients']['client0.org{}.{}'.format(c+1, self.domain)]['client']['clientPrivateKey'] = OrderedDict()
            key = os.listdir('{2}/crypto-config/peerOrganizations/org{0}.{1}/users/User1@org{0}.{1}/msp/keystore/'.format(c+1, self.domain, self.path))[0]
            doc['clients']['client0.org{}.{}'.format(c+1, self.domain)]['client']['clientPrivateKey']['path'] = 'crypto-config/peerOrganizations/org{0}.{1}/users/User1@org{0}.{1}/msp/keystore/{2}'.format(c+1, self.domain, key)
            doc['clients']['client0.org{}.{}'.format(c+1, self.domain)]['client']['clientSignedCert'] = OrderedDict()
            doc['clients']['client0.org{}.{}'.format(c+1, self.domain)]['client']['clientSignedCert']['path'] = 'crypto-config/peerOrganizations/org{0}.{1}/users/User1@org{0}.{1}/msp/signcerts/User1@org{0}.{1}-cert.pem'.format(c+1, self.domain)
        doc['channels'] = OrderedDict()
        doc['channels'][self.channel['name']] = OrderedDict()
        doc['channels'][self.channel['name']]['created'] = True
        doc['channels'][self.channel['name']]['definition'] = OrderedDict()
        doc['channels'][self.channel['name']]['definition']['capabilities'] = []
        # TODO - Fix to right consortium
        doc['channels'][self.channel['name']]['definition']['consortium'] = self.channel['consortium_name']
        doc['channels'][self.channel['name']]['definition']['msps'] = ['Org{}MSP'.format(i) for i in self.consortium]
        doc['channels'][self.channel['name']]['definition']['version'] = 0
        doc['channels'][self.channel['name']]['orderers'] = ['orderer{}.{}'.format(i+1, self.domain) for i in range(self.numOrds)]
        doc['channels'][self.channel['name']]['peers'] = OrderedDict()
        for o in range(self.numOrgs):
            for p in range(self.numPeers):
                doc['channels'][self.channel['name']]['peers']['peer{}.org{}.{}'.format(p, o+1, self.domain)] = OrderedDict()
                doc['channels'][self.channel['name']]['peers']['peer{}.org{}.{}'.format(p, o+1, self.domain)]['eventSource'] = True
        doc['channels'][self.channel['name']]['chaincodes'] = [OrderedDict() for i in range(len(self.contracts))]
        for c in range(len(self.contracts)):
            doc['channels'][self.channel['name']]['chaincodes'][c]['id'] = self.contracts[c]['id']
            doc['channels'][self.channel['name']]['chaincodes'][c]['version'] = self.contracts[c]['version']
            doc['channels'][self.channel['name']]['chaincodes'][c]['language'] = 'node'
            doc['channels'][self.channel['name']]['chaincodes'][c]['path'] = 'chaincode/{}'.format(self.contracts[c]['id'])
        doc['organizations'] = OrderedDict()
        for o in range(self.numOrgs):
            doc['organizations']['Org{}'.format(o+1)] = OrderedDict()
            doc['organizations']['Org{}'.format(o+1)]['mspid'] = 'Org{}MSP'.format(o+1)
            doc['organizations']['Org{}'.format(o+1)]['peers'] = ['peer{}.org{}.{}'.format(p, o+1, self.domain) for p in range(self.numPeers)]
            doc['organizations']['Org{}'.format(o+1)]['certificateAuthorities'] = ['ca.org{}.{}'.format(o+1, self.domain)]
            doc['organizations']['Org{}'.format(o+1)]['adminPrivateKey'] = OrderedDict()
            key = os.listdir('{2}/crypto-config/peerOrganizations/org{0}.{1}/users/Admin@org{0}.{1}/msp/keystore/'.format(o+1, self.domain, self.path))[0]
            doc['organizations']['Org{}'.format(o+1)]['adminPrivateKey']['path'] = 'crypto-config/peerOrganizations/org{0}.{1}/users/Admin@org{0}.{1}/msp/keystore/{2}'.format(o+1, self.domain, key)
            doc['organizations']['Org{}'.format(o+1)]['signedCert'] = OrderedDict()
            doc['organizations']['Org{}'.format(o+1)]['signedCert']['path'] = 'crypto-config/peerOrganizations/org{0}.{1}/users/Admin@org{0}.{1}/msp/signcerts/Admin@org{0}.{1}-cert.pem'.format(o+1, self.domain)
        doc['orderers'] = OrderedDict()
        for o in range(self.numOrds):
            doc['orderers']['orderer{}.{}'.format(o+1, self.domain)] = OrderedDict()
            doc['orderers']['orderer{}.{}'.format(o+1, self.domain)]['url'] = 'grpcs://localhost:7050'
            doc['orderers']['orderer{}.{}'.format(o+1, self.domain)]['grpcOptions'] = OrderedDict()
            doc['orderers']['orderer{}.{}'.format(o+1, self.domain)]['grpcOptions']['ssl-target-name-override'] = 'orderer{}.{}'.format(o+1, self.domain)
            doc['orderers']['orderer{}.{}'.format(o+1, self.domain)]['tlsCACerts'] = OrderedDict()
            doc['orderers']['orderer{}.{}'.format(o+1, self.domain)]['tlsCACerts']['path'] = 'crypto-config/ordererOrganizations/{0}/orderers/orderer{1}.{0}/msp/tlscacerts/tlsca.{0}-cert.pem'.format(self.domain, o+1)
        doc['peers'] = OrderedDict()
        doc['certificateAuthorities'] = OrderedDict()
        for o in range(self.numOrgs):
            with open('{}/connection-org{}.json'.format(self.path, o+1), 'r') as file:
                obj = json.load(file)
                peers = obj['peers']
                cas = obj['certificateAuthorities']
                for p in range(self.numPeers):
                    doc['peers']['peer{}.org{}.{}'.format(p, o+1, self.domain)] = OrderedDict()
                    doc['peers']['peer{}.org{}.{}'.format(p, o+1, self.domain)]['url'] = peers['peer{}.org{}.{}'.format(p, o+1, self.domain)]['url']
                    doc['peers']['peer{}.org{}.{}'.format(p, o+1, self.domain)]['grpcOptions'] = OrderedDict()
                    doc['peers']['peer{}.org{}.{}'.format(p, o+1, self.domain)]['grpcOptions']['ssl-target-name-override'] = peers['peer{}.org{}.{}'.format(p, o+1, self.domain)]['grpcOptions']['ssl-target-name-override']
                    doc['peers']['peer{}.org{}.{}'.format(p, o+1, self.domain)]['tlsCACerts'] = OrderedDict()
                    doc['peers']['peer{}.org{}.{}'.format(p, o+1, self.domain)]['tlsCACerts']['path'] = 'crypto-config/peerOrganizations/org{0}.{1}/peers/peer{2}.org{0}.{1}/msp/tlscacerts/tlsca.org{0}.{1}-cert.pem'.format(o+1, self.domain, p)
                doc['certificateAuthorities']['ca.org{}.{}'.format(o+1, self.domain)] = OrderedDict()
                doc['certificateAuthorities']['ca.org{}.{}'.format(o+1, self.domain)]['url'] = cas['ca.org{}.{}'.format(o+1, self.domain)]['url']
                doc['certificateAuthorities']['ca.org{}.{}'.format(o+1, self.domain)]['caName'] = 'ca-org{}'.format(o+1)
                doc['certificateAuthorities']['ca.org{}.{}'.format(o+1, self.domain)]['httpOptions'] = OrderedDict()
                doc['certificateAuthorities']['ca.org{}.{}'.format(o+1, self.domain)]['httpOptions']['verify'] = False
                doc['certificateAuthorities']['ca.org{}.{}'.format(o+1, self.domain)]['tlsCACerts'] = OrderedDict()
                doc['certificateAuthorities']['ca.org{}.{}'.format(o+1, self.domain)]['tlsCACerts']['path'] = 'crypto-config/peerOrganizations/org{0}.{1}/tlsca/tlsca.org{0}.{1}-cert.pem'.format(o+1, self.domain)
                doc['certificateAuthorities']['ca.org{}.{}'.format(o+1, self.domain)]['registrar'] = [OrderedDict()]
                doc['certificateAuthorities']['ca.org{}.{}'.format(o+1, self.domain)]['registrar'][0]['enrollId'] = 'admin'
                doc['certificateAuthorities']['ca.org{}.{}'.format(o+1, self.domain)]['registrar'][0]['enrollSecret'] = 'adminpw'
        with open('{}/benchmarks/{}/caliper_network.yaml'.format(self.path, self.project_name), 'w') as file:
            yaml.dump(doc, file, default_flow_style=False)

    def create_caliper(self):
        print("[*] Files will be generated in '%s'" % self.path)
        print("[+] Generating compose for Caliper...", end='')
        self.create_compose_caliper()
        print("DONE")
        print("[+] Generating network file...", end='')
        self.create_network_file()
        print("DONE\n")

    def build_caliper(self, project_name=None):
        if project_name is not None:
            self.project_name = project_name
        self.create_caliper()
        print("[+] Building Caliper Instance...", end='')
        self.caliper.instantiateCaliper()
        print("DONE\n")

class ComposeMqtt(object):
    
    def __init__(self, number_organizations, domain_name, net_names, 
                 swarm_length=1):
        if isinstance(net_names, str):
            net_names = tuple([net_names])
        if not isinstance(net_names, tuple):
            net_names = tuple(net_names)
        if not isinstance(swarm_length, tuple):
            swarm_length = tuple(swarm_length for i in range(number_organizations))
        self.path = path + 'mqtt/'
        self.numOrgs = number_organizations
        self.domain = domain_name
        self.netNames = net_names
        self.swarm_length = swarm_length

    def create_env(self):
        with open('{}.env'.format(self.path), 'w+') as file:
            text = 'COMPOSE_PROJECT_NAME={}'.format(self.project_name)
            file.write(text)
            
    def create_compose_mqtt(self):
        doc = OrderedDict()
        doc['version'] = '2'
        doc['networks'] = OrderedDict()
        # Creating Multiple networks if wanted (bridge between BC and EMR)
        for net in self.netNames:
            doc['networks'][net] = None
        swarm = []
        for org in range(self.numOrgs):
            for instance in range(self.swarm_length[org]):
                port1 = str(7883 + 1000*len(swarm))
                port2 = str(7001 + 1000*len(swarm))
                mosquitto = OrderedDict()
                mosquitto['image'] = "eclipse-mosquitto"
                mosquitto['container_name'] = 'mosquitto{}.org{}.{}'.format(instance, 
                         org + 1, self.domain)
                mosquitto['volumes'] = ['./config:/mosquitto/config',
                                        './certs{}:/mosquitto/certs'.format(instance)]
                mosquitto['ports'] = ['{}:8883'.format(port1),
                                      '{}:9001'.format(port2)]
                mosquitto['networks'] = list(self.netNames)
                swarm.append(mosquitto)
        doc['services'] = OrderedDict((c['container_name'],c) for c in swarm)
        with open('{}docker-compose-mqtt.yaml'.format(self.path), 'w') as file:
            yaml.dump(doc, file, default_flow_style=False)
        
    def create_mqtt(self, project_name='net'):
        self.project_name = project_name
        print("[*] Files will be generated in '%s'" % self.path)
        print("[+] Generating compose for MQTT...", end='')
        self.create_compose_mqtt()
        print("DONE")
        print("[+] Generating environmental variable file...", end='')
        self.create_env()
        print("DONE\n")
            
class ComposeEMR(object):
    
    def __init__(self, number_emrs, domain_name, net_name):
        if not isinstance(number_emrs, int):
            raise Exception("Argument 'number_emrs' must be an integer")
        if isinstance(net_name, list) and len(net_name) > 1:
            raise Exception("Argument 'net_name' must be singular.")
        elif isinstance(net_name, list):
            net_name = net_name[0]
        self.path = path + 'emr/'
        self.numEmrs = number_emrs
        self.domain = domain_name
        self.netName = net_name
        
    def create_env(self):
        with open('{}.env'.format(self.path), 'w+') as file:
            text = 'COMPOSE_PROJECT_NAME={}\n'.format(self.project_name)
            for e in range(self.numEmrs):
                text += 'SQL_PASSWORD{}={}\n'.format(e, self.passwords[e])
            file.write(text)
    
    def create_compose_emr(self):
        doc = OrderedDict()
        doc['version'] = '2'
        doc['volumes'] = OrderedDict()
        doc['networks'] = OrderedDict()
        doc['networks'][self.netName] = None
        emrs = []
        for e in range(self.numEmrs):
            port1 = str(7080 + 1000*e)
            port2 = str(7443 + 1000*e)
            # Creating necessary volumes
            doc['volumes']['openemr{}.{}'.format(e, self.domain)] = None
            doc['volumes']['openemr{}_db'.format(e)] = None
            doc['volumes']['openemr{}_assets'.format(e)] = None
            doc['volumes']['openemr{}_sites'.format(e)] = None
            doc['volumes']['openemr{}_modules'.format(e)] = None
            doc['volumes']['openemr{}_logs'.format(e)] = None
            doc['volumes']['openemr{}_vendor'.format(e)] = None
            doc['volumes']['openemr{}_ccda'.format(e)] = None
            # EMR instances
            emr = OrderedDict()
            emr['image'] = 'jacastillo8/openemr:latest'
            emr['container_name'] = 'openemr{}.{}'.format(e, self.domain)
            emr['ports'] = ['{}:80'.format(port1),
                            '{}:443'.format(port2)]
            emr['volumes'] = ['openemr{}.{}:/var/www/html/openemr'.format(e, self.domain),
                              'openemr{}_db:/var/lib/mysql'.format(e),
                              'openemr{}_assets:/var/www/html/openemr/public'.format(e),
                              'openemr{}_sites:/var/www/html/openemr/sites/default'.format(e),
                              'openemr{}_modules:/var/www/html/openemr/interface/modules/zend_modules/config'.format(e),
                              'openemr{}_logs:/var/log'.format(e),
                              'openemr{}_vendor:/var/www/html/openemr/vendor'.format(e),
                              'openemr{}_ccda:/var/www/html/openemr/ccdaservice'.format(e)]
            emr['environment'] = ['MYSQL_ROOT_PASSWORD=$SQL_PASSWORD{}'.format(e)]
            emr['networks'] = [self.netName]
            emrs.append(emr)
        # Generating DB Manager
        admin = OrderedDict()
        admin['image'] = 'phpmyadmin/phpmyadmin'
        admin['container_name'] = 'admin.{}'.format(self.domain)
        admin['ports'] = ['7040:80']
        hosts = ', '.join([h['container_name'] for h in emrs])
        admin['environment'] = ['PMA_HOSTS={}'.format(hosts)]
        admin['networks'] = [self.netName]
        # Updating doc file
        doc['services'] = OrderedDict((c['container_name'], c) for c in emrs + [admin])
        with open('{}docker-compose-emr.yaml'.format(self.path), 'w') as file:
            yaml.dump(doc, file, default_flow_style=False)

    # For multiple EMRs add passwords in list format    
    def create_emr(self, project_name='net', passwords=['root']):
        self.project_name = project_name
        if not isinstance(passwords, list):
            raise Exception("Argument 'passwords' must be a list")
        elif len(passwords) != self.numEmrs:
            warnings.warn("Mismatch length between instances and passwords. Defaulting passwords ['pass1', 'pass2',..., 'passN']")  
            self.passwords = ['root{}'.format(e) for e in range(self.numEmrs)]
        # Check if password is not the same for multiple instances
        elif len(set(passwords)) != len(passwords):
            raise Exception("Argument 'passwords' must have unique elements")
        else:
            self.passwords = passwords
        print("[*] Files will be generated in '%s'" % self.path)
        print("[+] Generating compose for EMRs...", end='')
        self.create_compose_emr()
        print("DONE")
        print("[+] Generating environmental variable file...", end='')
        self.create_env()
        print("DONE\n")
        
            
            
        
   
    
        