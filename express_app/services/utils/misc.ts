const fs = require('fs');
const path = require('path');
const hash = require('object-hash');
const { exec } = require('child_process');

import { Wallets, Gateway, DefaultEventHandlerStrategies, DefaultQueryHandlerStrategies } from "fabric-network";
import { Client, Organization } from "./factories";
import { Endpoint } from "./interfaces";

export function getCCP(organizationName: string, owner: string) {
    const ccpPath = path.join(__dirname, '..', '..', '..', 'blockchain_base', 'chains', `bc_${owner}`, `connection-${organizationName}.json`);
    const ccpJSON = fs.readFileSync(ccpPath, 'utf8');
    return JSON.parse(ccpJSON);
}

export function getWallet(organizationName: string, owner: string) {
    const walletPath = path.join(__dirname, '..', '..', '..', 'blockchain_base', 'chains', `bc_${owner}`, 'wallets', `wallet_${organizationName}`);
    return Wallets.newFileSystemWallet(walletPath);
}

export function getMSP(organizationName: string): string {
    return organizationName.charAt(0).toUpperCase() + organizationName.slice(1) + 'MSP';
}

export async function prepareEndpoint(endpoint: Endpoint, owner: string) {
    const ccp = await getCCP(endpoint.affiliation, owner);
    const wallet = await getWallet(endpoint.affiliation, owner);
    const gateway = new Gateway();
    await gateway.connect(ccp, { wallet, identity: endpoint.requestor, discovery: { enabled: true, asLocalhost: true }, 
                                eventHandlerOptions: { endorseTimeout: 300, commitTimeout: 300, strategy: DefaultEventHandlerStrategies.MSPID_SCOPE_ALLFORTX },
                                queryHandlerOptions: { timeout: 60, strategy: DefaultQueryHandlerStrategies.MSPID_SCOPE_SINGLE }});

    const network = await gateway.getNetwork(endpoint.channel.toLowerCase());
    const contract = await network.getContract(endpoint.contract);
    return {contract, gateway};
}

export function isUsernameExists(client: Client, users: Client[]) {
    for (let i = 0; i < users.length; i++) {
        if (client.enrollmentID === users[i].enrollmentID) return true;
    }
    return false;
}
/*async function getChannel(Endpoint) {
    const ccp = await getCCP(Endpoint.affiliation);
    const wallet = await getWallet(Endpoint.affiliation);

    const gateway = new Gateway();
    await gateway.connect(ccp, { wallet, identity: Endpoint.requestor, discovery: { enabled: true, asLocalhost: true }});

    const network = await gateway.getNetwork(Endpoint.channel);
    // getMspids() - check array for number of orgs
    // getEndorsers() - check array for peers
    // getCommitters() - check array length for number of ords
    return network.getChannel().getCommitters();
}*/

export function removeBCFiles(owner: string) {
    const filesPath = path.join(__dirname, '..', '..', '..', 'blockchain_base', 'chains', `bc_${owner}`)
    try {
        fs.rmSync(filesPath, { recursive: true, force: true });
        console.log(`[-] Directory "bc_${owner}" removed.`)
        return true;
    } catch (err) {
        console.log(err);
        return false;
    }
}

export function shell(cmd: string) {
    if (typeof cmd !== 'string') return Promise.reject('Command is not string');
    else {
        const command = cmd.replace(/\s*[\n\r]+\s*/g, ' ');

        let stdout = '';
        let stderr = '';

        return new Promise(function(resolve, reject) {
            const process = exec(command);

            process.stdout.setEncoding('utf8');
            process.stderr.setEncoding('utf8');

            process.stdout.on('data', function(data: any) {
                stdout += data.toString();
            });
            process.stderr.on('data', function(data: any) {
                stderr += data.toString();
            });

            process.on('error', function(error: any) {
                let result = {error: error, stdout: stdout, stderr: stderr};
                reject(result);
            });
            process.on('close', function(code: any) {
                let result = {code: code, stdout: stdout, stderr: stderr};
                resolve(result);
            });
        });
    }
}

export function containsObject(obj: Object, list: Object[]) {
    let id = hash(obj)
    for (let i = 0; i < list.length; i++) {
        if (hash(list[i]) === id) {
            return i.toString();
        }
    }

    return false;
}

/*export function isArray(obj: Object) {
    if (Array.isArray(obj)) return obj;
    else return [obj];
}*/

export function isDuplicate(arr: Organization[]){
    let values = arr.map((item) => item.name);
    return values.some((item, idx) => values.indexOf(item) != idx);
}

export function wait(delay=500) {
    return new Promise(resolve => setTimeout(resolve, delay));
}
