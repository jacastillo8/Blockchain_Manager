import subprocess, os, docker

# TODO - Set environmental variables for certs (scripts/utils.sh)
def setGlobals(peer, org, domain, port):
    globals = {}
    globals['ORDERER_CA'] = '/opt/gopath/src/github.com/hyperledger/fabric/peer/crypto/ordererOrganizations/{0}/orderers/orderer1.{0}/msp/tlscacerts/tlsca.{0}-cert.pem'.format(domain)
    globals['CORE_PEER_ADDRESS'] = 'peer{}.org{}.{}:{}'.format(peer, org, domain, port)
    globals['CORE_PEER_LOCALMSPID'] = 'Org{}MSP'.format(org)
    globals['CORE_PEER_TLS_ROOTCERT_FILE'] = "/opt/gopath/src/github.com/hyperledger/fabric/peer/crypto/peerOrganizations/org{0}.{1}/peers/peer{2}.org{0}.{1}/tls/ca.crt".format(org, domain, peer)
    globals['CORE_PEER_MSPCONFIGPATH'] = "/opt/gopath/src/github.com/hyperledger/fabric/peer/crypto/peerOrganizations/org{0}.{1}/users/Admin@org{0}.{1}/msp".format(org, domain)
    return globals

# TODO - use peer to create channel
def createChannel():
    return

class Fabric:
    def __init__(self, basePath='', arm=False):
        self.type = 'vanilla'
        self.base = basePath[:-1]
        if arm:
            self.type = 'arm'
        self.bin = '{}/bin/{}'.format(self.base, self.type)

    def newCryptoMaterial(self):
        command = "{}/cryptogen generate --config={}/crypto-config.yaml".format(self.bin, self.base)
        p = subprocess.Popen(command.split(), 
                            bufsize=-1, 
                            executable=None, 
                            stdin=None, 
                            stdout=None, 
                            stderr=None, 
                            preexec_fn=None, 
                            close_fds=True, 
                            shell=False, 
                            cwd=self.base).wait()
        print("[+] 'CRYPTO-CONFIG' folder generated with certificates.")

    def newGenesisBlock(self):
        command = "{}/configtxgen -profile EtcdRaft -channelID net-sys-channel -outputBlock {}/channel-artifacts/genesis.block".format(self.bin, self.base)
        p = subprocess.Popen(command.split(),
                            bufsize=-1, 
                            executable=None, 
                            stdin=None, 
                            stdout=None, 
                            stderr=None, 
                            preexec_fn=None, 
                            close_fds=True, 
                            shell=False, 
                            cwd=self.base).wait()
        print("[+] Genesis Block Generated.")

    def newChannelConfiguration(self, profile, channelID):
        command = "{0}/configtxgen -profile {1} -outputCreateChannelTx {2}/channel-artifacts/{3}.tx -channelID {4}".format(self.bin, profile, self.base, profile.lower(), channelID.lower())
        p = subprocess.Popen(command.split(),
                            bufsize=-1, 
                            executable=None, 
                            stdin=None, 
                            stdout=None, 
                            stderr=None, 
                            preexec_fn=None, 
                            close_fds=True, 
                            shell=False, 
                            cwd=self.base).wait()
        print("[+] Channel Configuration Generated.")

    def newAnchorUpdate(self, profile, consortium, channelID):
        for c in consortium:
            command = "{0}/configtxgen -profile {1} -outputAnchorPeersUpdate {2}/channel-artifacts/Org{3}MSPanchors_{4}.tx -channelID {4} -asOrg Org{3}MSP".format(self.bin, profile, self.base, c, channelID.lower())
            subprocess.Popen(command.split(),                            
                            bufsize=-1, 
                            executable=None, 
                            stdin=None, 
                            stdout=None, 
                            stderr=None, 
                            preexec_fn=None, 
                            close_fds=True, 
                            shell=False, 
                            cwd=self.base).wait()
        print("[+] Anchor Peer Updates Generated.")
    
    def instantiateNetwork(self, orgs, domain):
        for o in range(orgs):
            files = os.listdir('{}/crypto-config/peerOrganizations/org{}.{}/ca'.format(self.base, o+1, domain))
            selected = [f for f in files if '_sk' in f]
            os.environ['NET_CA{}_PRIVATE_KEY'.format(o+1)] = selected[0]
        compose_files = ['docker-compose.yaml', 'docker-compose-ca.yaml',
                        'docker-compose-couch.yaml', 'docker-compose-etcdraft2.yaml']
        command = "docker-compose -f " + " -f ".join(compose_files) + " up -d"
        p = subprocess.Popen(command.split(),
                            bufsize=-1, 
                            executable=None, 
                            stdin=None, 
                            stdout=None, 
                            stderr=None, 
                            preexec_fn=None, 
                            close_fds=True, 
                            shell=False, 
                            cwd=self.base).wait()
        print('[+] Network Up.')

    def createChannel(self, org, domain, ports, channelName, channelID):
        client = docker.from_env()
        cli = client.containers.get('cli')
        globals = setGlobals('0', org, domain, ports['peer0.org{}.{}'.format(org, domain)])
        orderer = 'orderer1.{}:{}'.format(domain, ports['orderer1.{}'.format(domain)])
        command = 'peer channel create -o {} -c {} -f ./channel-artifacts/{}.tx --tls {} --cafile {} >&log.txt'.format(orderer, channelID.lower(), channelName.lower(), 'true', globals['ORDERER_CA'])
        result = cli.exec_run(command, environment=globals)
        if result[0] != 0:
            print('Error during channel creation')
    
    def updateAnchorPeers(self, peer, org, domain, ports, channelID):
        client = docker.from_env()
        cli = client.containers.get('cli')
        globals = setGlobals(peer, org, domain, ports['peer{}.org{}.{}'.format(peer, org, domain)])
        orderer = 'orderer1.{}:{}'.format(domain, ports['orderer1.{}'.format(domain)])
        command = 'peer channel update -o {0} -c {1} -f ./channel-artifacts/{2}anchors_{1}.tx --tls {3} --cafile {4} >&log.txt'.format(orderer, channelID.lower(), globals['CORE_PEER_LOCALMSPID'], 'true', globals['ORDERER_CA'])
        result = cli.exec_run(command, environment=globals)
        if result[0] != 0:
            print('Error while updating Peer{}:\n{}'.format(peer, result[1]))

    def joinChannel(self, peer, org, domain, ports, channelID):
        client = docker.from_env()
        cli = client.containers.get('cli')
        globals = setGlobals(peer, org, domain, ports['peer{}.org{}.{}'.format(peer, org, domain)])
        command = 'peer channel join -b {}.block >&log.txt'.format(channelID.lower())
        result = cli.exec_run(command, environment=globals)
        if result[0] != 0:
            print('Error in Peer{} while joining channel {}:\n{}'.format(peer, channelID, result[1]))

    def installContract(self, peer, org, domain, ports, contract_name, contract_version):
        client = docker.from_env()
        cli = client.containers.get('cli')
        contract_path = "/opt/gopath/src/github.com/chaincode/{}/".format(contract_name[:-1])
        globals = setGlobals(peer, org, domain, ports['peer{}.org{}.{}'.format(peer, org, domain)])
        command = 'peer chaincode install -n {} -v {} -l node -p {}'.format(contract_name, contract_version, contract_path)
        result = cli.exec_run(command, environment=globals)
        if result[0] != 0:
            print('Error in Peer{} while installing contract "{}":\n{}'.format(peer, contract_name[:-1], result[1]))

    def instantiateContract(self, org, domain, ports, contract_name, contract_version, channelID):
        client = docker.from_env()
        cli = client.containers.get('cli')
        globals = setGlobals(0, org, domain, ports['peer0.org{}.{}'.format(org, domain)])
        command = 'peer chaincode instantiate -n {} -v {} -l node -C {} --tls --cafile {}'.format(contract_name, contract_version, channelID.lower(), globals['ORDERER_CA']) 
        command += " --collections-config scripts/collections.json -c '{\"Args\":[\"init\"]}'"
        # NOTES - May need to change policies to query from other channel
        command += ' -P "OR(\'Org{}MSP.peer\')"'.format(org)
        #command += ' -P "OR(\'Org1MSP.peer\',\'Org2MSP.peer\')"'
        #print(command)
        result = cli.exec_run(command, environment=globals)
        #print(result)
        if result[0] != 0:
            print('Error in Peer0 while instantiating contract "{}":\n{}'.format(contract_name[:-1], result[1]))

    def upgradeContract(self, peer, org, domain, ports, contract_name, contract_version, channelID):
        client = docker.from_env()
        cli = client.containers.get('cli')
        globals = setGlobals(peer, org, domain, ports['peer{}.org{}.{}'.format(peer, org, domain)])
        contract_path = "/opt/gopath/src/github.com/chaincode/{}/".format(contract_name[:-1])
        command = "peer chaincode upgrade -n {} -v {} -c '{\"Args\":[\"init\"]}' -p {} -C {}".format(contract_name, contract_version, contract_path, channelID.lower())
        result = cli.exec_run(command, environment=globals)
        if result[0] != 0:
            print('Error in Peer{} while instantiating contract "{}":\n{}'.format(peer, contract_name[:-1], result[1]))
        
class Caliper:
    def __init__(self, basePath):
        self.base = basePath

    def instantiateCaliper(self):
        command = "docker-compose -f docker-compose-caliper.yaml up -d"
        p = subprocess.Popen(command.split(),
                            bufsize=-1, 
                            executable=None, 
                            stdin=None, 
                            stdout=None, 
                            stderr=None, 
                            preexec_fn=None, 
                            close_fds=True, 
                            shell=False, 
                            cwd=self.base).wait()