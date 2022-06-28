const shim = require('fabric-shim');

var Chaincode = class {

    async Init(stub) {
        return shim.success();
    }

    // WARNING: Invoke function is fully functional for most simple applications. However, there may be scenarios where you 
    // may be required to change its behavior (i.e., embedding ACLs). Therefore, modify at your own risk. 
    // ========================================================================
    async Invoke(stub) {
        try {
            const ret = stub.getFunctionAndParameters();
            const method = this[ret.fcn];
            if (method === undefined) throw Error('Method does not exists');
            const payload = await method(stub, ret.params);
            return shim.success(payload);
        } catch (err) {
            return shim.error(err);
        }
    }
    // ========================================================================

    /**
     * Returns empty JSON string to show a transactions has been successfully committed.
     *
     * @param {object} stub Chaincode interface.
     * @param {object} args Array containing passed arguments, i.e., args, data.
     * @return {buffer} Buffer of string, i.e., JSON object.
     */
    async insertSimple(stub, args) {
        const type = JSON.parse(args[0]).type;
        const data = JSON.parse(args[1]);
        await stub.putState(type, Buffer.from(JSON.stringify({ tx: data, 
            timestamp: stub.getTxTimestamp().seconds.low })));
        return Buffer.from(JSON.stringify({}));
    }

    /**
     * Returns JSON document extracted from ledger.
     *
     * @param {object} stub Chaincode interface.
     * @param {object} args Array containing passed arguments, i.e., args.
     * @return {buffer} Buffer of string, i.e., JSON object.
     */
    async getSimple(stub, args) {
        const type = JSON.parse(args[0]).type;
        const buffer = await stub.getState(type);
        const string = buffer.toString('utf8');
        if (string !== '') return Buffer.from(JSON.stringify(JSON.parse(string)));
        return Buffer.from(JSON.stringify({}));
    }

    /**
     * Returns empty JSON string to show a private transactions has been successfully committed.
     *
     * @param {object} stub Chaincode interface.
     * @param {object} args Array containing passed arguments, i.e., args, data.
     * @return {buffer} Buffer of string, i.e., JSON object.
     */
    async insertPrivate(stub, args) {
        const type = JSON.parse(args[0]).type;
        const data = JSON.parse(args[1]);
        // Private collections are accessed according to Organization ID. For example, Organization 1 accesses collectionPrivate1.
        const mspId = stub.getCreator().mspid.match(/\d/g)[0];
        await stub.putPrivateData(`collectionPrivate${mspId}`, type, Buffer.from(JSON.stringify({ tx: data, 
            timestamp: stub.getTxTimestamp().seconds.low })));
        return Buffer.from(JSON.stringify({}));
    }

    /**
     * Returns JSON document extracted from private ledger.
     *
     * @param {object} stub Chaincode interface.
     * @param {object} args Array containing passed arguments, i.e., args.
     * @return {buffer} Buffer of string, i.e., JSON object.
     */
    async getPrivate(stub, args) {
        const type = JSON.parse(args[0]).type;
        const buffer = await stub.getPrivateData(`collectionPrivate${mspId}`, type);
        const obj = JSON.parse(buffer.toString('utf8'));
        return Buffer.from(JSON.stringify(obj));
    }
}

shim.start(new Chaincode());