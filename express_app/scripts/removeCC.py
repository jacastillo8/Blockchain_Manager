import docker
import argparse
import sys
import re

def remove(client, objects, type='containers'):
    if len(objects) > 0:
        print('[+] Removing CC {}...'.format(type), end='')
        # Stop CC containers and Remove
        for i in objects:
            if type == 'containers':
                obj = client.containers.get(i['id'])
                obj.stop()
                obj.remove()
            elif type == 'images':
                #obj = client.images.get(i['id'])
                client.images.remove(i['id'])
        print('DONE')

client = docker.from_env()
parser = argparse.ArgumentParser(description='Removes ChainCode (CC) instances from docker environment.')
parser.add_argument('-n', '--name', dest='name', type=str, help='ChainCode Name')
parser.add_argument('-v', '--version', dest='version', type=str, help='ChainCode Version')
parser.add_argument('-d', '--domain', dest='domain', type=str, help='Domain Name')

if len(sys.argv) == 1:
    cc_name = 'dev'
    cc_version = 'peer'
    print('[*] Attempting to remove ALL ChainCodes from the Blockchain')
    # Get peers for peer cc clensing
    peers = [p for p in client.containers.list() if re.search(r'peer', p.name)]
    # Remove CC from container directories
    print('[+] Removing CC objects...', end='')
    for peer in peers:
        peer.exec_run('rm *', workdir='/var/hyperledger/production/chaincodes')
    print('DONE')
else:
    args = parser.parse_args()
    cc_name = args.name
    cc_version = args.version
    cc_domain = args.domain
    print('[*] Attempting to remove the following ChainCode from the Blockchain: {}-{}'.format(cc_name, cc_version))
    # Get peers for peer cc clensing
    peers = [p for p in client.containers.list() if re.search(r'peer.*{}'.format(cc_domain), p.name) is not None]
    # Remove CC from container directories
    print('[+] Removing CC objects...', end='')
    for peer in peers:
        peer.exec_run('rm {}.{}'.format(cc_name, cc_version), workdir='/var/hyperledger/production/chaincodes')
    print('DONE')

# Get CC containers
cc_conts = [{"id": i.id, "name": i.name} for i in client.containers.list() if re.search(r'dev-.*{}-{}-{}'.format(cc_domain, cc_name, cc_version), i.name)]
remove(client, cc_conts, type='containers')
# Images to remove
cc_images = [{"id": i.id.replace('sha256:', '')} for i in client.images.list() if re.search(r'dev-.*{}-{}-{}'.format(cc_domain, cc_name, cc_version), i.tags[0])]
remove(client, cc_images, type='images')