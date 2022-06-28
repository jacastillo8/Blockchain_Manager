"""
Created on Thur Apr  29 21:34:13 2021
Last Update on Thur Apr  29 2021
@author: Jorge Castillo
@email: jacastillo8@outlook.com
"""
from build_compose.compose import ComposeCaliper

import argparse
import sys, json, os, re

def contract(s):
    separator = r'[ ;]'
    try:
        for l in re.split(separator, s):
            contract = tuple(map(str, l.split(',')))
            contract = { 'id': contract[0], 'version': contract[1] }
        return contract
    except:
        raise argparse.ArgumentTypeError("Consortiums must be given divided by commas and space, dot, or semicolon e.g.: 'x,y k,l,m'")

def consortium(s):
    separator = r'[ ;.]'
    try:
        for l in re.split(separator, s):
            consortium = tuple(set(map(int, l.split(','))))
        return consortium
    except:
        raise argparse.ArgumentTypeError("Consortiums must be given divided by commas and space, dot, or semicolon e.g.: 'x,y k,l,m'")
 
     
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Creates necessary configuration files for Caliper container for benchmark analysis.')
    parser.add_argument('-O', '--organizations', dest='orgs', type=int, help='Number of Organizations.')
    parser.add_argument('-p', '--peers', dest='peers', default=1, type=int, help='Number of Peers')
    parser.add_argument('-C', '--channel', dest='channel', default='mychannel', nargs='+', help='Names of desired channels.')
    parser.add_argument('-c', dest='consort', default='1', nargs='+',  type=consortium, help='List the sets of consortiums: a,b c,d,f')
    parser.add_argument('-o', dest='ords', default=1, type=int, help='Number of Orderers for Consensus.')
    parser.add_argument('-d', dest='domain', default='example.com', type=str, help='Domain name for the application (example.com).')
    parser.add_argument('--contracts', dest='contracts', default='', nargs='+', type=contract, help='List the sets of contracts: name,version')

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)

    args = parser.parse_args()

    if len(args.contracts) == 0 :
        sys.exit(1) 
    ComposeCaliper(number_organizations=args.orgs,
                   number_peers=args.peers,
                   number_orderers=args.ords,
                   channel=args.channel,
                   consortium=args.consort[0],
                   domain_name=args.domain,
                   contracts=args.contracts).build_caliper()