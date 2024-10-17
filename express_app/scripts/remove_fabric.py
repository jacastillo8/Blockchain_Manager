import sys, argparse, os, re, docker

def remove_containers(client, target):
    containers = client.containers.list(all=True)
    for c in containers:
        if target == c.name.split('.')[-1]:
            c.stop()
            c.remove(v=True)

def remove_orphan_volumes(client, target):
    volumes = client.volumes.list(filters={'dangling': 'true'})
    for v in volumes:
        if target in v.name:
            v.remove()

def remove_networks(client, target):
    networks = client.networks.list()
    for n in networks:
        if target in n.name:
            n.remove()

parser = argparse.ArgumentParser(description='Removes target containers from docker environment.')
parser.add_argument('-t', '--target', dest='target', type=str, help='BC owner to remove.')

if len(sys.argv) == 1:
    parser.print_help()
    sys.exit(1)

args = parser.parse_args()

client = docker.from_env()

# Remove target containers
remove_containers(client, args.target)

#Remove target volumes
remove_orphan_volumes(client, args.target)

#Remove target networks
remove_networks(client, args.target)