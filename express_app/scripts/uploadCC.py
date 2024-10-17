# CHECK CONTRACT FOLDER IN BLOCKCHAIN_BASE TO YIELD DIFFERENT ERROR

from build_compose.compose import ComposeFabric
import sys, argparse, os, re, docker

def consortium(s):
    separator = r'[ ;.]'
    try:
        for l in re.split(separator, s):
            consortium = tuple(set(map(int, l.split(','))))
        return consortium
    except:
        raise argparse.ArgumentTypeError("Consortiums must be given divided by commas and space, dot, or semicolon e.g.: 'x,y k,l,m'")
 
parser = argparse.ArgumentParser(description='Uploads ChainCode (CC) instances to docker environment.')
parser.add_argument('-O', '--organizations', dest='orgs', type=int, help='Number of Organizations.')
parser.add_argument('-p', '--peers', dest='peers', default='1', nargs='+', help='Number of Peers per Organization. ' + 
                        'It can be an integer (symmetric) or tuple (Ex: -p 1,2).')
parser.add_argument('-C', '--channel', dest='channel', type=str, help='Channel Name where CC will function')
parser.add_argument('-c', dest='consort', default='1', nargs='+',  type=consortium, help='List the sets of consortiums: a,b c,d,f')
parser.add_argument('-d', '--domain', dest='domain', type=str, help='Domain name')
parser.add_argument('-n', '--name', dest='name', type=str, help='Contract Name')
parser.add_argument('-v', '--version', dest='version', type=str, help='ChainCode Version')
parser.add_argument('-o', dest='org', default=None, type=str, help='Contract Organization')
parser.add_argument('--folder', dest='path', default='', type=str, help='Folder where it will be stored')

if len(sys.argv) == 1:
    parser.print_help()
    sys.exit(1)

args = parser.parse_args()

if ',' in args.peers[0]:
    args.peers = args.peers[0].split(',')
if len(args.peers) == 1:
    peers = int(args.peers[0])
else:
    peers = tuple(int(p) for p in args.peers)

# TODO - Check number_organizations
fabric = ComposeFabric(subpath=args.path,
                        number_organizations=args.orgs,
                        number_peers=peers,
                        org_users=1,
                        channels=[args.channel],
                        consortiums=list(set(args.consort)),
                        consensus='etcdraft', 
                        block_form=['1s', '10', '10MB'],
                        domain_name=args.domain,
                        net_name='blockchain',
                        db='couchdb')
fabric.install_contract(args.name, args.version, args.org)