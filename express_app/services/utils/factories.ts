const hash = require('object-hash');

export class Admin {
    public type: string = 'admin';
    constructor(public enrollmentID: string, public org: string, public enrollmentSecret: string) {}
} 

export class Client {
    public type: string = 'client';
    constructor(public enrollmentID: string, public org: string, public department: string) {}
}

export class Contract {
    public id: string;
    public belongsTo: string;

    constructor(public channel: string, public name: string, public version: string, belongsTo: string) {
        this.belongsTo = belongsTo || "All";
        this.id = hash({ name: this.name, version: this.version, channel: this.channel, 
            belongsTo: this.belongsTo });
    }
}

export class Organization {
    public peers: string;
    constructor(public name: string, public id: string, numberOfPeers: string, public users: Client[]) {
        this.peers = numberOfPeers;
    }
}