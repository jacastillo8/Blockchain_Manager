import { Contract, Client } from "./utils/factories";

const hash = require('object-hash');
let Chain = require('../models/chain');

export function storeChainId(obj: Object, bid: string) {
    let chain = new Chain(obj);
    chain.id = bid;
    chain.save();
}

export function updateChainId(bid: string, contracts: Contract[]) {
    Chain.findOne({ id: bid }, function(err: any, doc: any) {
        if (doc !== null) {
            doc.status = !doc.status;
            for (let i=0; i< doc.channels.lenght; i++) {
                let channelName = doc.channels[i].name;
                doc.channels[i].contracts = [];
                for (let j=0; j < contracts.length; j++) {
                    let contract = contracts[i];
                    if (channelName === contract.channel) {
                        doc.channels[i].contracts.push({ name: contract.name, version: contract.version });
                    }
                }
            }
            doc.save();
        }
    });
}

export function updateChainBenchmark(bid: string) {
    Chain.findOne({ id: bid }, function(err: any, doc: any) {
        if (doc !== null) {
            doc.benchmark = !doc.benchmark;
            doc.save();
        }
    })
}

export function removeChainId(bid: string) {
    Chain.findOne({ id: bid }, function(err: any, doc: any) {
        if (doc !== null) {
            doc.remove();
        }
    });
}

export function appendNewChainUser(client: Client, bid: string) {
    let filter = { 'id': bid, 'orgs.id': client.org };
    let request = { $addToSet: { 'orgs.$.users': client }}
    Chain.updateOne(filter, request, function(err: any, doc: any) {});
}

export function appendNewChainContract(contract: any, bid: string) {
    let data = { name: contract.name, version: contract.version };
    let filter = { 'id': bid, 'channels.name': contract.channel };
    let request = { $addToSet: { 'channels.$.contracts': data }};
    Chain.updateOne(filter, request, function(err: any, doc: any) {});
}

export function appendNewChannel(channel: any, bid: string) {
    let data = { name: channel.name, orgs: channel.orgs, contracts: channel.contracts };
    let filter = { 'id': bid };
    let request = { $addToSet: { 'channels': data }}
    Chain.updateOne(filter, request, function(err: any, doc: any) {})
}
export async function searchChainId(bid: string) {
    let document = null;
    let doc: any;
    let error: any;
    try {
        document = await Chain.findOne({ id: bid }).exec();
        error = '';
    } catch (err) {
        error = err;
    }
    if (document !== null) {
        doc = {
            orgs: document.orgs,
            owner: document.owner,
            orderers: document.orderers,
            consensus: document.consensus,
            channels: document.channels,
            //contracts: document.contracts,
            block: document.block,
            status: document.status,
            benchmark: document.benchmark,
            id: document.id
        };
    } else doc = '';

    return { doc, error };
}

export async function generateChainId(obj: any) {
    let id = hash(obj.owner);
    let { doc } = await searchChainId(id);
    if (!doc) return id;
    return null;
}