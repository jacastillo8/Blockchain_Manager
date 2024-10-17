# -*- coding: utf-8 -*-
"""
Created on Mon Jan 13 17:47:13 2020
Last Update on Mon Jan  28 2020
@author: Jorge Castillo
@email: jacastillo8@outlook.com
"""
from build_compose.compose import ComposeFabric

import argparse, itertools
import sys
import re

avail_protos = ['solo', 'etcdraft']    
avail_dbs = ['lvldb', 'couchdb']   

def consortium(s):
    separator = r'[ ;.]'
    try:
        for l in re.split(separator, s):
            consortium = tuple(set(map(int, l.split(','))))
        return consortium
    except:
        raise argparse.ArgumentTypeError("Consortiums must be given divided by commas and space, dot, or semicolon e.g.: 'x,y k,l,m'")
       
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Creates necessary configuration files for Docker containers, ' + 
                                     'cryptographic certificates, and connection profiles to generate a fully ' + 
                                     'functional Hyperledger Fabric Blockchain.')
    parser.add_argument('-O', '--organizations', dest='orgs', type=int, help='Number of Organizations.')
    parser.add_argument('-p', '--peers', dest='peers', default='1', nargs='+', help='Number of Peers per Organization. ' + 
                        'It can be an integer (symmetric) or tuple (Ex: -p 1,2).')
    parser.add_argument('-u', '--users', dest='users', default=1, nargs='+', type=int, help='Number of Users per Organization. ' + 
                        'It can be an integer (symmetric) or tuple (Ex: -u 2 5).')
    parser.add_argument('-C', '--channels', dest='channels', default='mychannel', nargs='+', help='Names of desired channels.')
    parser.add_argument('-c', dest='consorts', default='1', nargs='+',  type=consortium, help='List the sets of consortiums: a,b c,d,f')
    parser.add_argument('-o', dest='ords', default='4', type=str, help='Number of Orderers for Consensus.')
    parser.add_argument('-d', dest='domain', default='example.com', type=str, help='Domain name for the application (example.com).')
    parser.add_argument('-n', dest='net', default='blockchain', type=str, help='Network name for Docker network.')
    parser.add_argument('-D', '--database', dest='db', default='couchdb', type=str, help='Database to use in Blockchain.')
    parser.add_argument('--credentials', dest='creds', default='', nargs='+', type=list, 
                        help='Database credentials (Ex: --credentials user password).')
    parser.add_argument('--arm64', dest='arch', default='false', type=str, help='Processor Architecture.')
    parser.add_argument('--block', dest='block', nargs='+', help='Underlying block structure.')
    parser.add_argument('--folder', dest='path', default='', type=str, help='Folder where it will be stored')
    
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)
    args = parser.parse_args()
    if ',' in args.peers[0]:
        args.peers = args.peers[0].split(',')
    # Error Handling
    if len(args.peers) > args.orgs or len(args.users) > args.orgs:
        parser.error("Number of peers or users cannot exceed the number of available organizations ({}).".format(args.orgs))
    elif not args.db.lower() in avail_dbs:
        parser.error("Available options for databases are: 'lvldb' and 'couchdb'.")
    elif (len(args.creds) == 1 and args.creds[0] != '') or (isinstance(args.creds, list) and len(args.creds) > 2):
        parser.error("Invalid credentials. Set only username and password.")
    elif len(args.consorts) != len(args.channels):
        parser.error("Number of channels does not match the number of consortiums.")
    arr = set([i for sub in args.consorts for i in sub])
    if max(arr) > args.orgs:
        parser.error("Organization in consortium does not exist.")
    if len(arr) != args.orgs:
        parser.error("At least one Organization does not belong to a Consortium.")
    c = []
    for r in range(len([i for i in range(args.orgs)]) -1):
        c += list(itertools.combinations([i for i in range(args.orgs)], r))
    if len(args.channels) > (len(c) + args.orgs):
        parser.error("Channels exceed max amount of allowed combinations ({}) for given organizations ({})".format(len(c), args.orgs))
    # Argument Manipulation
    if len(args.peers) == 1:
        peers = int(args.peers[0])
    else:
        peers = tuple(int(p) for p in args.peers)
    if len(args.users) == 1:
        users = args.users[0]
    else:
        users = tuple(args.users)
    # Setting architecture type
    arch = False
    if args.arch == 'true':
        arch = True
    # Generate Files
    ComposeFabric(subpath=args.path,
                number_organizations=args.orgs,
                number_peers=peers,
                org_users=users,
                channels=args.channels,
                consortiums=list(set(args.consorts)),
                consensus='etcdraft', 
                block_form=args.block,
                domain_name=args.domain,
                net_name=args.net,
                db=args.db,
                db_creds=args.creds,
                arm64=arch).build_fabric(orderers=int(args.ords))

