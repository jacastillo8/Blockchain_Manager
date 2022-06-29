'use strict'

import { Enrollment } from "./Enrollment";
import { Admin, Client, Contract, Organization } from "./utils/factories";
import { BlockStructure, Channel, Endpoint, Message } from "./utils/interfaces";

const { shell, containsObject, isDuplicate, prepareEndpoint, wait,
        isUsernameExists } = require('./utils/misc');

/*function extractPeers(organizations) {
    let peers = [];
    for (let i=0; i < organizations.length; i++) {
        peers.push(organizations[i].peers);
    }
    return peers;
}*/

function extractOrgs(organizations: any[]) {
    let orgs: Organization[] = [];
    for (let i=0; i < organizations.length; i++) {
        let org = organizations[i];
        let users: Client[] = [];
        for (let j=0; j < org.users.length; j++) {
            let user = org.users[j];
            users.push(new Client(user.enrollmentID, org.name, user.department));
        }
        let peers: any = process.env.PEERS;
        orgs.push(new Organization(org.name, `org${i + 1}`, peers, users))
    }
    if (isDuplicate(orgs)) throw new Error('Duplicate organization name found');
    else return orgs;
}

function extractUsers(organizations: Organization[]) {
    let totalUsers: Client[] = [];
    for (let i=0; i < organizations.length; i++) {
        let users = organizations[i].users;
        for (let j=0; j < users.length; j++) {
            let user = users[j];
            totalUsers.push(new Client(user.enrollmentID, `org${i + 1}`, user.department));
        }
    }
    return totalUsers;
}

function extractContracts(channels: Channel[]) {
    let parsedContracts: Contract[] = [];
    for (let i=0; i < channels.length; i++) {
        let channel = channels[i];
        let contracts = channel.contracts;
        for (let j=0; j < contracts.length; j++) {
            let contract: any = contracts[j];
            parsedContracts.push(new Contract(channel.name, contract.name, contract.version, contract.belongsTo));
        }
    }
    return parsedContracts;
}

async function getPythonEnv() {
    let python = 'python';
    let pythonVersion = await shell(`${python} -c "import platform; print(platform.python_version())"`);
    if (pythonVersion.stdout[0] !== '3') python = 'python3';
    return python;
}

export class Blockchain {
    private _owner: string;
    private _block: BlockStructure;
    private _orderers: number;
    private _consensus: string;
    private _organizations: Organization[];
    private _channels: Channel[];
    private _users: Client[];
    private _built: boolean;
    private _init_benchmark: boolean;
    private _contracts: Contract[];

    constructor(orderers: number, orgs: Object[], owner: string, channels: Channel[], status: boolean, block: BlockStructure, init_benchmark: boolean) {
        this._owner = owner;
        this._block = block;
        this._orderers = orderers;
        this._consensus = (this._orderers > 1) ? 'etcdraft': 'solo';
        this._organizations = extractOrgs(orgs);
        this._channels = channels;
        // TODO - get peers from each organization
        //this._peers = extractPeers(this._organizations);
        this._users = extractUsers(this._organizations);
        this._built = status || false;
        this._init_benchmark = init_benchmark || false; 
        this._contracts = extractContracts(this._channels);
    }

    get info() {
        return {
            owner: this._owner,
            orderers: this._orderers,
            consensus: this._consensus,
            block: this._block,
            orgs: this._organizations,
            channels: this._channels,
            status: this._built,
            init_benchmark: this._init_benchmark
        }
    }

    get contracts() {
        return this._contracts;
    }

    contract(cid: string) {
        if (cid !== null) {
            let contract = this._contracts.find(function(contract) {
                                return contract.id === cid;
                            });
            if (contract !== undefined) return contract;
            return {};
        } else throw new Error('Invalid Contract ID');

    }

    users(organizationName: string ='') {
        if (!organizationName) return this._users;
        else {
            let org = this._organizations.find(function(org) {
                return org.name === organizationName;
            });
            if (org !== undefined) return org.users;
            return [];
        }
    }

    async build(setListeners=false) {
        try {
            if (!this._built) {
                let python = await getPythonEnv();
                let orgs = this._organizations.length;
                // TODO - Get peers from orgs
                let peers = process.env.PEERS;
                let scriptPath = 'scripts/build_fabric.py';
                let channelNames = this._channels.map(c => c.name);
                let consortiums = this._channels.map(c => {
                    let channelOrgs = c.orgs;
                    let matchingOrgs = this._organizations.filter(entry => channelOrgs.includes(entry.name))
                    let orgIDs = matchingOrgs.map(o => o.id.slice(3));
                    return orgIDs.join(',')
                });
                let blockParams = `--block ${this._block.timeout} ${this._block.batch_size.max_messages} ${this._block.batch_size.max_bytes}`;
                let args = `-O ${orgs} -p ${peers} -u 1 -o ${Number(this._orderers) - 1} -d ${this._owner.toLowerCase()} -n blockchain -C ${channelNames.join(' ')} -c ${consortiums.join(' ')} ${blockParams}`;
                console.log(`[+] Executing: ${python} ${scriptPath} ${args}`);
                let result = await shell(`${python} ${scriptPath} ${args}`);
                console.log('[+] Network generated');
                if (result.code === 0) {
                    console.log('[+] Enrolling users...');
                    //let user = new Client('benchmark_user', this._organizations[0].name, 'Benchmark');
                    //this._users.push(user);
                    this._users.forEach(function(this: Blockchain, user: Client) {
                        this.enroll(user);
                    }, this);
                    for (let i = 0; i < this._contracts.length; i++) {
                        let contract = this._contracts[i];
                        try {
                            await this.installContract(contract.channel, contract.name, contract.version, contract.belongsTo);
                        } catch (err) {
                            let index = containsObject(contract, this._contracts);
                            if (index > -1) {
                                this._contracts.splice(index, 1);
                                console.log('[!] Contract not found');
                            }
                        }
                    }
                    //this._users.pop();
                    this._built = true;
                } else {
                    throw Error(JSON.stringify(result.stderr));
                }
            } else {
                console.log('[!] Blockchain created already');
            }
            return this.info
        } catch (err: any) {
            throw new Error(err.message);
        }

    }

    // TODO - create method to generate channels ()

    // Future: need to remove only containers related to specific domain
    /*async destroy() {
        console.log(`[+] Executing: bash ./scripts/clean.sh`);
        let result = await shell('bash ./scripts/clean.sh');
        if (result.code === 0) {
            this._built = false;
        }
        return result;
    }*/

    async enroll(client: Client) {
        let enroll = new Enrollment();
        if (containsObject(client, this._users) && this._built) {
            throw new Error('User already exists');
        // INTRODUCE ELSE-IF TO CHECK UNIQUENESS OF USER ID REGARDLESS OF DEPARTMENT
        } else if (isUsernameExists(client, this._users) && this._built) {
            throw new Error('User ID already exists');
        } else {
            if (parseInt(client.org.replace(/\D/g, "")) > this._organizations.length) throw new Error('Organization does not exist')
            else {
                try {
                    // Get admin identity, enroll admin if not enrolled
                    let adminIdentity = await enroll.admin(new Admin('admin', client.org, 'adminpw'));
                    await enroll.client(client, adminIdentity);
                } catch (error) {
                    console.log(`[!] Failed to enroll user:\n${error}`);
                }
            }
        }
    }

    async installContract(channel: string, name: string, version: string, belongsTo: string) {
        let contract = new Contract(channel, name, version, belongsTo);
        let cid: string = '';
        if (containsObject(contract, this._contracts) && this._built) {
            throw new Error('Contract already installed.');
        }
        else {
            let python = await getPythonEnv();
            let orgs = this._organizations.length;
            // TODO - Get peers from orgs
            let peers = process.env.PEERS;
            let scriptPath = 'scripts/uploadCC.py';
            let channelNames = this._channels.map(c => c.name);
            let index = channelNames.indexOf(channel);
            if (index < 0) throw Error('Channel does not exists.');
            let consortiums = this._channels.map(c => {
                let channelOrgs = c.orgs;
                let matchingOrgs = this._organizations.filter(entry => channelOrgs.includes(entry.name))
                let orgIDs = matchingOrgs.map(o => o.id.slice(3));
                return orgIDs.join(',')
            });
            // Check which orgs I need to install the contract to
            
            let result: any;
            if (contract.belongsTo === "All") {
                let args = `-O ${orgs} -p ${peers} -C ${channel} -c ${consortiums[index]} -d ${this._owner.toLowerCase()} -n ${name + version[0]} -v ${version}`;
                console.log(`[+] Executing: ${python} ${scriptPath} ${args}`);
                result = await shell(`${python} ${scriptPath} ${args}`);
            } else {
                let orgID = this._organizations.filter(entry => entry.name === belongsTo)[0].id;
                let args = `-O ${orgs} -p ${peers} -C ${channel} -c ${consortiums[index]} -d ${this._owner.toLowerCase()} -n ${name + orgID.slice(-1)} -v ${version} -o ${orgID.slice(-1)}`;
                console.log(`[+] Executing: ${python} ${scriptPath} ${args}`);
                result = await shell(`${python} ${scriptPath} ${args}`);
            }
            //console.log(result)
            if (result.code === 0) cid = contract.id;
            // Check response code - changes from 0 to 1
            else throw new Error(`Exception caused by: ${result.stderr}`);
        }
        if (!containsObject(contract, this._contracts)) this._contracts.push(contract);
        // Wait 5s for CC instantiation to complete
        //await wait(5000);
        console.log('[!] Contract instantiation complete');
        return { cid };
    }

    // Future - removing containers is a hassle
    /*async removeContract(contract) {
        console.log('[+] Removing contract...');
        let result = containsObject(contract, this._contracts);
        if (result) {
            let response = await shell(`python ./scripts/removeCC.py -n ${contract.name} -v ${contract.version} -d ${this._owner.toLowerCase()}`);
            if (response.code === 0) {
                this._contracts.splice(parseInt(result), 1);
                return true;
            }
            else console.log(`Exception found: ${response.stderr}`);
        }
        console.log('Contract not found')
        return false;
    }*/

    async buildCaliper(channel: string) {
        let python = await getPythonEnv()
        let orgs = this._organizations.length;
        let peers = process.env.PEERS;
        let channelNames = this._channels.map(c => c.name);
        let index = channelNames.indexOf(channel);
        if (index < 0) throw Error('Channel does not exists.');
        let consortiums = this._channels.map(c => {
            let channelOrgs = c.orgs;
            let matchingOrgs = this._organizations.filter(entry => channelOrgs.includes(entry.name))
            let orgIDs = matchingOrgs.map(o => o.id.slice(3));
            return orgIDs.join(',')
        });
        let contracts = ''
        for (let i=0; i<this._contracts.length; i++) {
            let obj = { id: this._contracts[i].name, version: this._contracts[i].version };
            contracts += `${obj.id},${obj.version} `;
        }
        let scriptPath = 'scripts/build_caliper.py';
        let args = `-O ${orgs} -p ${peers} -C ${channel} ${index + 1} -c ${consortiums[index]} -o ${this._orderers} -d ${this._owner.toLowerCase()}`;
        args += ` --contracts ${contracts}`;
        console.log(`[+] Executing: ${python} ${scriptPath} ${args}`);
        let result = await shell(`${python} ${scriptPath} ${args}`);
        if (result.code === 0) {
            console.log('[+] Hyperledger Caliper is Up');
        } else throw Error(`Caliper Instantiation Failed with Error: ${result.stderr}`);
    }

    async evaluate(message: Message, endpoint: Endpoint, json=false) {
        console.log('[+] Evaluating transaction...');
        const { contract, gateway } = await prepareEndpoint(endpoint);
        let buffer = await contract.evaluateTransaction(message.method, JSON.stringify(message.args), JSON.stringify(message.data));
        await gateway.disconnect();
        if (json) return JSON.parse(buffer.toString());
        else return buffer;
    }

    async submit(message: Message, endpoint: Endpoint, json=false) {
        try {
            console.log('[+] Submiting transaction...');
            const { contract, gateway } = await prepareEndpoint(endpoint);
            let buffer = await contract.submitTransaction(message.method, JSON.stringify(message.args), JSON.stringify(message.data));
            await gateway.disconnect();
            // Wait 2s to avoid Phantom read errors
            //await wait(2000);
            if (json) return JSON.parse(buffer.toString());
            else return buffer;
        } catch (err: any) {
            throw Error(err.message);
        }

    }
}

module.exports.Blockchain = Blockchain;