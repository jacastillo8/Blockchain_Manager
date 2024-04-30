const express = require('express');
const multer = require('multer');
const fs = require('fs');

const Transaction = require('../models/transaction');
const Chain = require('../models/chain');

const { Blockchain } = require('../services/Blockchain');
const { storeChainId, updateChainId, appendNewChainUser, 
    generateChainId, searchChainId, appendNewChainContract, 
    updateChainBenchmark, appendNewChannel } = require('../services/ChainModel');
const MAX_CHUNK_SIZE = 28; // MB - FUTURE: PROVIDED IN UTILS

const router = express.Router();

const storage = multer.diskStorage({
    destination: function(req, file, cb) {
        cb(null, './uploads');
    }, 
    filename: function(req, file, cb) {
        cb(null, `${Date.now()}.${file.originalname.split('.')[1]}`);
    }
});

const fileFilter = function(req, file, cb) {
    // FUTURE: IMPLEMENT FILTER DEFINITION DEPENDING ON CONTRACTS
    if (file.originalname.split('.')[1] !== 'exe') cb(null, true);
    else cb(new Error('Invalid File'), false);
}

const upload = multer({ 
    storage: storage, 
    limits: { 
        // FUTURE: DEFINE ACCORDING TO APPLICATION CONTRACT - AI OFTEN HAVE MODELS OF > 500MB
        fileSize: 1024 * 1024 * 600 
    }, 
    fileFilter: fileFilter
});

// Middlewares
async function checkChainId(req, res, next) {
    let bid = req.params.bid;
    let { doc, error } = await searchChainId(bid);
    if (error) res.status(500).json({ message: error.message });
    else if (doc) {
        res.locals.doc = doc;
        next();
        return
    }
    else res.status(404).json({});
}

function isBodyEmpty(req, res, next) {
    if (Object.keys(req.body).length === 0 && req.header('Content-Type').split(';')[0] === 'application/json') {
        res.status(400).json({ message: 'Invalid Request' });
        return;
    } // IMPLEMENT CHECK IF EMPTY IMAGE
    next();
}

function prepareEndpoint(req, res, next) {
    let doc = res.locals.doc;
    let bc = new Blockchain(doc.orderers, doc.orgs, doc.owner, doc.channels, doc.status, doc.block, doc.init_benchmark);
    let contract = bc.contract(req.params.cid);
    if (contract.length !== 0) {
        let users = bc.users();
        let affiliation = getAffiliation(req.body.requestor, users);
        res.locals.endpoint = { 
            requestor: req.body.requestor,
            affiliation,
            channel: contract.channel
        };
        if (contract.belongsTo === 'All') res.locals.endpoint['contract'] = contract.name + contract.version[0];
        else res.locals.endpoint['contract'] = contract.name + affiliation.slice(-1);
    } else {
        res.status(400).json({ message: 'Contract not Found' });
        return
    }
    next();
    return
}

// Routes
router.get('/chains', async function(req, res) {
    let chains = await Chain.find({});
    if (chains.length > 0) {
        chains = chains.map((item) => {
            return {bid: item.id, owner: item.owner};
        });
    }
    res.status(200).json(chains);
});

router.post('*', isBodyEmpty);
router.all('/:bid*', checkChainId);

router.post('/', async function(req, res) {
    let body = req.body;
    let bid = await generateChainId(body);
    if (bid !== null) {
        try {
            let bc = new Blockchain(body.orderers, body.orgs, body.owner, body.channels, body.status, body.block, body.init_benchmark);
            storeChainId(bc.info, bid);
            res.status(201).json({ bid });
        } catch (err) {
            res.status(400).json({ message: err.message });
        }
    } else res.status(400).json({ message: 'Owner can only own a single Blockchain' });
});

router.get('/:bid', async function(req, res) {
    let doc = res.locals.doc;
    let bc = new Blockchain(doc.orderers, doc.orgs, doc.owner, doc.channels, doc.status, doc.block, doc.init_benchmark);
    res.json(bc.info);
});

/*router.delete('/:bid', async function(req, res) {
    let doc = res.locals.doc;
    let bc = new Blockchain(doc.orderers, doc.orgs, doc.owner);
    // MISSING A PROPER CLEAN METHOD
    await bc.clean();
    removeChainId(bid);
    res.json({});
});*/

router.get('/:bid/block', function(req, res) {
    let doc = res.locals.doc;
    let bc = new Blockchain(doc.orderers, doc.orgs, doc.owner, doc.channels, doc.status, doc.block, doc.init_benchmark);
    res.json(bc.info.block);
});

router.get('/:bid/channel', function(req, res) {
    let doc = res.locals.doc;
    let bc = new Blockchain(doc.orderers, doc.orgs, doc.owner, doc.channels, doc.status, doc.block, doc.init_benchmark);
    res.json(bc.info.channels);
});

router.post('/:bid/channel', async function(req, res) {
    let doc = res.locals.doc;
    let channel = req.body;
    let bc = new Blockchain(doc.orderers, doc.orgs, doc.owner, doc.channels, doc.status, doc.block, doc.init_benchmark);
    // TODO - Instantiate channel with contracts
    appendNewChannel(channel, doc.id);
    res.status(201).json({});
})

router.get('/:bid/build', async function(req, res) {
    try {
        let doc = res.locals.doc;
        if (!doc.status) {
            let bc = new Blockchain(doc.orderers, doc.orgs, doc.owner, doc.channels, doc.status, doc.block, doc.init_benchmark);
            let info = await bc.build(setListeners=true);
            if (info.status) {
                updateChainId(doc.id, bc.contracts);
                // TODO - create listeners
                res.json({ status: info.status, contracts: info.contracts });
            }
        } else res.status(409).json({ message: 'Resource built already' });
    } catch (err) {
        res.status(500).json({ message: err.message });
    }
});

router.post('/:bid/benchmark', async function(req, res) {
    try {
        let doc = res.locals.doc;
        let bc = new Blockchain(doc.orderers, doc.orgs, doc.owner, doc.channels, doc.status, doc.block, doc.init_benchmark);
        if (!bc.info.status) throw Error('Resource not initialized');
        if (!bc.info.init_benchmark) {
            let info = bc.info;
            info.id = doc.id;
            await bc.buildCaliper(req.body.channel);
            //updateChainBenchmark(info.id);
            res.json({});
            return;
        }
        throw Error('Caliper is already running');
    } catch (err) {
        res.status(500).json({ message: err.message });
    }
});

router.get('/:bid/config/:orgName', function(req, res) {
    let doc = res.locals.doc;
    let bc = new Blockchain(doc.orderers, doc.orgs, doc.owner, doc.channels, doc.status, doc.block, doc.init_benchmark);
    let enrolledOrgs = bc.info.orgs;
    for (let i=0; i<enrolledOrgs.length; i++) {
        let org = enrolledOrgs[i];
        if (org.name === req.params.orgName) {
            res.download(`${__dirname}/../../blockchain_base/connection-${org.id.toLowerCase()}.json`);
            return
        }
    }
    res.status(400).json({ message: 'Connection Profile does not exists.'})
})

router.get('/:bid/wallet/:userName/:orgName', function(req, res) {
    let doc = res.locals.doc;
    let bc = new Blockchain(doc.orderers, doc.orgs, doc.owner, doc.channels, doc.status, doc.block, doc.init_benchmark);
    let enrolledOrgs = bc.info.orgs;
    for (let i=0; i<enrolledOrgs.length; i++) {
        let org = enrolledOrgs[i];
        if (org.name === req.params.orgName) {
            let enrolledUsers = bc.users(org.name);
            for (let j=0; j<enrolledUsers.length; j++) {
                let user = enrolledUsers[j];
                if (user.enrollmentID === req.params.userName) {
                    res.download(`${__dirname}/../wallets/wallet_${org.id}/${user.enrollmentID}.id`);
                    return;
                }
            }
        }
    }
    res.status(400).json({ message: 'User does not exists under given organization'})
});

router.get('/:bid/users', function(req, res) {
    let doc = res.locals.doc;
    let bc = new Blockchain(doc.orderers, doc.orgs, doc.owner, doc.channels, doc.status, doc.block, doc.init_benchmark);
    res.json({ users: bc.users()});
});

router.get('/:bid/users/:orgName', function(req, res) {
    let doc = res.locals.doc;
    let bc = new Blockchain(doc.orderers, doc.orgs, doc.owner, doc.channels, doc.status, doc.block, doc.init_benchmark);
    res.json({ users: bc.users(req.params.orgName)});
});

router.post('/:bid/users', async function(req, res) {
    let doc = res.locals.doc;
    let body = req.body;
    if (doc.status) {
        let bc = new Blockchain(doc.orderers, doc.orgs, doc.owner, doc.channels, doc.status, doc.block, doc.init_benchmark);
        let index = translateUserOrg(doc, body);
        if (index > -1) {
            try {
                body.org = doc.orgs[index].id;
                let client = { enrollmentID: body.name, org: body.org, department: body.department, type: "client" };
                await bc.enroll(client);
                appendNewChainUser(client, doc.id);
                res.status(201).json({});
            } catch (err) {
                res.status(400).json({ message: err.message });
            }
        } else res.status(400).json({ message: 'Username does not belong to a registered organization' })
    } else res.status(400).json({ message: 'Resource not initialized' });   
});

router.get('/:bid/contracts', function(req, res) {
    let doc = res.locals.doc;
    let bc = new Blockchain(doc.orderers, doc.orgs, doc.owner, doc.channels, doc.status, doc.block, doc.init_benchmark);
    res.json({ contracts: bc.contracts });
});

router.post('/:bid/contracts', async function(req, res) {
    let doc = res.locals.doc;
    let body = req.body;
    if (doc.status) {
        let bc = new Blockchain(doc.orderers, doc.orgs, doc.owner, doc.channels, doc.status, doc.block, doc.init_benchmark);
        try {
            let cid = await bc.installContract(body.channel, body.name, body.version);
            body.id = cid;
            appendNewChainContract(body, doc.id);
            res.status(201).json({ cid: cid.cid });
        } catch (err) {
            res.status(400).json({ message: err.message });
        }
    } else res.status(400).json({ message: 'Resource not initialized' });   
});

router.get('/:bid/contracts/:cid', function(req, res) {
    let doc = res.locals.doc;
    let bc = new Blockchain(doc.orderers, doc.orgs, doc.owner, doc.channels, doc.status, doc.block, doc.init_benchmark);
    res.json({ contract: bc.contract(req.params.cid) })
});

/*router.delete('/:bid/contracts/:cid', async function(req, res) {
    let doc = res.locals.doc;
    let bc = new Blockchain(doc);
    let contract = bc.contracts(req.params.cid);
    await bc.removeContract(contract);
    removeChainContract(contract);
});*/

// remove async
router.post('/:bid/:cid/document/insert', upload.single('document'), prepareEndpoint, function(req, res) {
    let doc = res.locals.doc;
    let bc = new Blockchain(doc.orderers, doc.orgs, doc.owner, doc.channels, doc.status, doc.block, doc.init_benchmark);
    let endpoint = res.locals.endpoint;
    req.body.message = JSON.parse(req.body.message);

    let bitmapStream = fs.createReadStream(req.file.path, { highWaterMark: MAX_CHUNK_SIZE * 1024 * 1024 });

    let buffers = [];
    bitmapStream.on('data', function(chunk) {
        buffers.push(chunk.toString('base64'));
    });

    let result = [];
    bitmapStream.on('end', async function() {
        removeFile(req.file.path);
        for (let i = 0; i < buffers.length; i++) {
            let encodedFile = {
                name: req.file.filename,
                id: i,
                file: buffers[i]
            };

            let message = {
                method: req.body.message.method,
                args: req.body.message.args,
                data: encodedFile
            };
            let startTime = Date.now();
            try {
                result.push(await bc.submit(message, endpoint, true));
                let newTX = new Transaction({
                    bid: req.params.bid,
                    cid: req.params.cid,
                    endpoint: message.method,
                    exceptionRaised: false,
                    type: 'insert',
                    inTransit: Date.now() - startTime //- 2000 // compensate for 2s added to avoid phantom read - check Blockchain.submit
                });
                await newTX.save();
            } catch (err) {
                let newTX = new Transaction({
                    bid: req.params.bid,
                    cid: req.params.cid,
                    endpoint: message.method,
                    exceptionRaised: true,
                    type: 'insert',
                    inTransit: Date.now() - startTime
                });
                newTX.save();
                res.status(500).json({ error: err.message });
                return 
            }
        }
        res.json({ filename: req.file.filename, output: result });
    });
});

router.post('/:bid/:cid/document/evaluate', prepareEndpoint, async function(req, res) {
    let doc = res.locals.doc;
    let bc = new Blockchain(doc.orderers, doc.orgs, doc.owner, doc.channels, doc.status, doc.block, doc.init_benchmark);
    let endpoint = res.locals.endpoint;

    let message = {
        method: req.body.message.method,
        args: req.body.message.args,
        data: {}
    }
    let startTime = Date.now();
    try {
        let result = await bc.evaluate(message, endpoint, true);
        parseFile(req.body.file, result);
        let newTX = new Transaction({
            bid: req.params.bid,
            cid: req.params.cid,
            endpoint: message.method,
            exceptionRaised: false,
            type: 'query',
            inTransit: Date.now() - startTime
        });
        newTX.save();
        res.download(`./uploads/${req.body.file}`, function(err) {
            if (err) console.log(err);
            removeFile(`./uploads/${req.body.file}`);
        });
    } catch (err) {
        let newTX = new Transaction({
            bid: req.params.bid,
            cid: req.params.cid,
            endpoint: message.method,
            exceptionRaised: true,
            type: 'query',
            inTransit: Date.now() - startTime
        });
        newTX.save();
        res.status(500).json({ error: err.message });
    }
});

router.post('/:bid/:cid/insert', prepareEndpoint, async function(req, res) {
    let doc = res.locals.doc;
    let bc = new Blockchain(doc.orderers, doc.orgs, doc.owner, doc.channels, doc.status, doc.block, doc.init_benchmark);
    let endpoint = res.locals.endpoint;

    let message = {
        method: req.body.message.method,
        args: req.body.message.args,
        data: req.body.message.data
    };
    let startTime = Date.now();
    try {
        let result = await bc.submit(message, endpoint, true);
        let newTX = new Transaction({
            bid: req.params.bid,
            cid: req.params.cid,
            endpoint: message.method,
            exceptionRaised: false,
            type: 'insert',
            inTransit: Date.now() - startTime //- 2000 // compensate for 2s added to avoid phantom read - check Blockchain.submit
        });
        newTX.save();
        res.json({ result });
    } catch (err) {
        let newTX = new Transaction({
            bid: req.params.bid,
            cid: req.params.cid,
            endpoint: message.method,
            exceptionRaised: true,
            type: 'insert',
            inTransit: Date.now() - startTime
        });
        newTX.save();
        res.status(500).json({ error: err.message });
    }
});

router.post('/:bid/:cid/evaluate', prepareEndpoint, async function(req, res) {
    let doc = res.locals.doc;
    let bc = new Blockchain(doc.orderers, doc.orgs, doc.owner, doc.channels, doc.status, doc.block, doc.init_benchmark);
    let endpoint = res.locals.endpoint;
    let message = {
        method: req.body.message.method,
        args: req.body.message.args,
        data: {}
    };
    let startTime = Date.now();
    try {
        let result = await bc.evaluate(message, endpoint, true);
        res.json({ result });
        let newTX = new Transaction({
            bid: req.params.bid,
            cid: req.params.cid,
            endpoint: message.method,
            exceptionRaised: false,
            type: 'query',
            inTransit: Date.now() - startTime
        });
        newTX.save();
    } catch (err) {
        let newTX = new Transaction({
            bid: req.params.bid,
            cid: req.params.cid,
            endpoint: message.method,
            exceptionRaised: true,
            type: 'query',
            inTransit: Date.now() - startTime
        });
        newTX.save();
        res.status(500).json({ error: err.message });
    }
});

// Helper Functions
function translateUserOrg(doc, user) {
    let org = null;
    for (let i=0; i < doc.orgs.length; i++) {
        org = doc.orgs[i];
        if (org.name === user.org) {
            return i;
        }
    }
    return -1;
}

function getAffiliation(user, users) {
    for (let i=0; i < users.length; i++) {
        if (user === users[i].enrollmentID) return users[i].org;
    }
    return null;
}

function removeFile(path) {
    console.log(`[!] Removing file: ${path}`);
    fs.unlink(path, function(err) {
        if (err) {
            throw new Error(err.message);
        }
    });
}

function parseFile(file, transactions) {
    let txs = [];
    for (let i = 0; i < transactions.length; i++) {
        var tx = transactions[i].Record.data;
        if (file === tx.name) {
            txs.push(tx);
            if (txs.length > 1) {
                txs.sort((a, b) => (a.id > b.id) ? 1 : -1);
            }
        }
    }
    let base64File = [];
    for (let i = 0; i < txs.length; i++) {
        base64File.push(new Buffer.from(txs[i].file, 'base64'));
    }
    base64File = Buffer.concat(base64File);
    fs.writeFileSync(`./uploads/${file}`, base64File);
}

module.exports = router;