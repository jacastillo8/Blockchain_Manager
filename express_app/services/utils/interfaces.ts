export interface FabricConfigurationProfile {
    name: string,
    version: string,
    client: Object,
    organizations: Object,
    peers: Object,
    certificateAuthorities: Object
}

export interface BlockStructure {
    timeout: string,
    batch_size: {
        max_messages: string,
        max_bytes: string
    }
}

export interface Channel {
    name: string;
    orgs: string[];
    contracts: Object[];
}

export interface Endpoint {
    affiliation: string,
    requestor: string,
    channel: string,
    contract: string
}

export interface Message {
    method: string,
    args: Object,
    data: Object
}