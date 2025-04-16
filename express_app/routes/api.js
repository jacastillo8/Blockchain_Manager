const express = require('express');
const multer = require('multer');
const fs = require('fs');
const path = require('path');
const logger = require('../services/utils/logger');

const Transaction = require('../models/transaction');
const Chain = require('../models/chain');

const { Blockchain } = require('../services/Blockchain');
const { storeChainId, updateChainId, appendNewChainUser, 
    generateChainId, searchChainId, appendNewChainContract, 
    updateChainBenchmark, appendNewChannel, removeChainId } = require('../services/ChainModel');

const { authenticateSession, isAdmin } = require('./auth');

const MAX_CHUNK_SIZE = 28; // MB - FUTURE: PROVIDED IN UTILS

const router = express.Router();

const storage = multer.diskStorage({
    destination: function(req, file, cb) {
        let owner = req.params.owner;
        // Create a directory based on the file name
        const uploadDir = path.join(__dirname, '..', '..', 'blockchain_base', 'chains', `bc_${owner}`, 'chaincode', req.body.name);

        // Check if the directory exists, if not, create it
        if (!fs.existsSync(uploadDir)) {
            fs.mkdirSync(uploadDir, { recursive: true });  // Create directory recursively
        }

        // Set the upload directory as the destination
        cb(null, uploadDir);
    }, 
    filename: function(req, file, cb) {
        if (path.extname(file.originalname) === '.js') cb(null, `${file.originalname}`);
        else cb(null, `package${path.extname(file.originalname)}`)
    }
});

const fileFilter = function(req, file, cb) {
    if (path.extname(file.originalname) === '.js' || path.extname(file.originalname) === '.json') cb(null, true);
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
    if (error) {
        logger.error(`function: checkChainId    status: 500 error ${error.message}`);
        res.status(500).json({ message: error.message });
    } else if (doc) {
        res.locals.doc = doc;
        next();
        return
    }
    else res.status(404).json({});
}

async function addParams(req, res, next) {
    let doc = res.locals.doc;
    req.params.owner = doc.owner;
    next();
    return;
}

function isBodyEmpty(req, res, next) {
    if (Object.keys(req.body).length === 0 && req.header('Content-Type').split(';')[0] === 'application/json') {
        logger.error("function: isBodyEmpty status: 400 error: Invalid request");
        res.status(400).json({ message: 'Invalid request' });
        return;
    } // IMPLEMENT CHECK IF EMPTY IMAGE
    next();
}

function prepareEndpoint(req, res, next) {
    let doc = res.locals.doc;
    let bc = new Blockchain(doc.orderers, doc.orgs, doc.owner, doc.channels, doc.status, doc.block, doc.benchmark);
    let contract = bc.contract(req.params.cid);
    if (Object.keys(contract).length !== 0) {
        let users = bc.users();
        let affiliation = getAffiliation(req.body.requestor, users);
        if (affiliation === null) {
            logger.error(`function: prepareEndpoint client: ${req.body.requestor} bid: ${doc.id}  cid: ${req.params.cid}  status: 400 error: Requestor not found`);
            res.status(400).json({ message: 'Requestor not found' });
            return;
        }
        res.locals.endpoint = { 
            requestor: req.body.requestor,
            affiliation,
            channel: contract.channel
        };
        if (contract.belongsTo === 'All') res.locals.endpoint['contract'] = contract.name + contract.version[0];
        else res.locals.endpoint['contract'] = contract.name + affiliation.slice(-1);
    } else {
        logger.error(`function: prepareEndpoint client: ${req.body.requestor} bid: ${doc.id}  cid: ${req.params.cid}  status: 400 error: Contract not found`);
        res.status(400).json({ message: 'Contract not found' });
        return
    }
    next();
    return
}

// Routes
router.get('/', async function(req, res) {
    let chains = await Chain.find({});
    logger.info("GET    /api    status: 200");
    res.status(200).json(chains);
});

router.post('*', isBodyEmpty);
router.all('/:bid*', checkChainId);

router.post('/', authenticateSession, isAdmin, async function(req, res) {
    let body = req.body;
    let bid = await generateChainId(body);
    if (bid !== null) {
        try {
            let bc = new Blockchain(body.orderers, body.orgs, body.owner, body.channels, body.status, body.block, body.benchmark);
            storeChainId(bc.info, bid);
            logger.info(`POST   /api    user: ${req.session.user.username}  bid: ${bid} status: 201`);
            res.status(201).json({ bid });
        } catch (err) {
            logger.error(`POST  /api    user: ${req.session.user.username}  bid: ${bid} status: 400 error: ${err.message}`);
            res.status(400).json({ message: err.message });
        }
    } else {
        logger.error(`POST  /api    user: ${req.session.user.username}  bid: ${bid} status: 400 error: Owner can only own a single Blockchain`);
        res.status(400).json({ message: 'Owner can only own a single Blockchain' });
    }
});

router.get('/:bid', async function(req, res) {
    let doc = res.locals.doc;
    let bc = new Blockchain(doc.orderers, doc.orgs, doc.owner, doc.channels, doc.status, doc.block, doc.benchmark);
    logger.info(`GET    /api/:bid   bid: ${doc.id}  status: 200`);
    res.json(bc.info);
});

router.delete('/:bid', authenticateSession, isAdmin, async function(req, res) {
    let doc = res.locals.doc;
    let bc = new Blockchain(doc.orderers, doc.orgs, doc.owner, doc.channels, doc.status, doc.block, doc.benchmark);
    let status = await bc.clean();
    if (!status) {
        logger.error(`DELETE    /api/:bid   user: ${req.session.user.username}  bid: ${doc.id}  status: 500 error: Unable to remove Blockchain`);
        res.status(500).json({});
        return;
    }
    removeChainId(doc.id);
    logger.info(`DELETE /api/:bid   user: ${req.session.user.username}  bid: ${doc.id}  status: 200`);
    res.json({});
});

router.get('/:bid/block', function(req, res) {
    let doc = res.locals.doc;
    let bc = new Blockchain(doc.orderers, doc.orgs, doc.owner, doc.channels, doc.status, doc.block, doc.benchmark);
    logger.info(`GET    /api/:bid/block    bid: ${doc.id}   status: 200`);
    res.json(bc.info.block);
});

router.get('/:bid/channel', function(req, res) {
    let doc = res.locals.doc;
    let bc = new Blockchain(doc.orderers, doc.orgs, doc.owner, doc.channels, doc.status, doc.block, doc.benchmark);
    logger.info(`GET    /api/:bid/channel   bid: ${doc.id}  status: 200`);
    res.json(bc.info.channels);
});

router.post('/:bid/channel', authenticateSession, isAdmin, async function(req, res) {
    let doc = res.locals.doc;
    let channel = req.body;
    let bc = new Blockchain(doc.orderers, doc.orgs, doc.owner, doc.channels, doc.status, doc.block, doc.benchmark);
    // TODO - Instantiate channel with contracts
    appendNewChannel(channel, doc.id);
    logger.info(`POST   /api/:bid/channel   user: ${req.session.user.username}   bid: ${doc.id}  status: 201`);
    res.status(201).json({});
})

router.get('/:bid/build', authenticateSession, isAdmin, async function(req, res) {
    try {
        let doc = res.locals.doc;
        if (!doc.status) {
            let bc = new Blockchain(doc.orderers, doc.orgs, doc.owner, doc.channels, doc.status, doc.block, doc.benchmark);
            let info = await bc.build();
            if (info.status) {
                updateChainId(doc.id, bc.contracts);
                // TODO - create listeners
                logger.info(`GET    /api/:bid/build user: ${req.session.user.username}   bid: ${doc.id}  status: 200`);
                res.json({ status: info.status, contracts: info.contracts });
            }
        } else {
            logger.error(`GET   /api/:bid/build user: ${req.session.user.username}   bid: ${doc.id}  status: 409 error: Resource built already`);
            res.status(409).json({ message: 'Resource built already' });
        }
    } catch (err) {
        logger.error(`GET   /api/:bid/build user: ${req.session.user.username}   bid: ${req.params.bid}  status: 500 error: ${err.message}`);
        res.status(500).json({ message: err.message });
    }
});

router.post('/:bid/benchmark', authenticateSession, isAdmin, async function(req, res) {
    try {
        let doc = res.locals.doc;
        let bc = new Blockchain(doc.orderers, doc.orgs, doc.owner, doc.channels, doc.status, doc.block, doc.benchmark);
        if (!bc.info.status) throw Error('Resource not initialized');
        if (!bc.info.benchmark) {
            let info = bc.info;
            info.id = doc.id;
            await bc.buildCaliper(req.body.channel);
            //updateChainBenchmark(info.id);
            logger.info(`POST   /api/:bid/benchmark user: ${req.session.user.username}   bid: ${doc.id}  status: 200`);
            res.json({});
            return;
        }
        throw Error('Caliper is already running');
    } catch (err) {
        logger.error(`POST  /api/:bid/benchmark user: ${req.session.user.username}   bid: ${doc.id}  status: 500 error: ${err.message}`)
        res.status(500).json({ message: err.message });
    }
});

router.get('/:bid/config/:orgName', function(req, res) {
    let doc = res.locals.doc;
    let bc = new Blockchain(doc.orderers, doc.orgs, doc.owner, doc.channels, doc.status, doc.block, doc.benchmark);
    let enrolledOrgs = bc.info.orgs;
    for (let i=0; i<enrolledOrgs.length; i++) {
        let org = enrolledOrgs[i];
        if (org.name === req.params.orgName) {
            logger.info(`GET    /api/:bid/config/:orgName   bid: ${doc.id}  orgName: ${org.name}    status: 200`);
            res.download(path.join(__dirname, '..', '..', 'blockchain_base', 'chains', `bc_${doc.owner}`, `connection-${org.id.toLowerCase()}.json`));
            return
        }
    }
    logger.error(`GET   /api/:bid/config/:orgName   bid: ${doc.id}  orgName: ${req.params.orgName}  status: 400 error: Connection Profile does not exists`);
    res.status(400).json({ message: 'Connection Profile does not exists'})
})

router.get('/:bid/wallet/:userName/:orgName', function(req, res) {
    let doc = res.locals.doc;
    let bc = new Blockchain(doc.orderers, doc.orgs, doc.owner, doc.channels, doc.status, doc.block, doc.benchmark);
    let enrolledOrgs = bc.info.orgs;
    for (let i=0; i<enrolledOrgs.length; i++) {
        let org = enrolledOrgs[i];
        if (org.name === req.params.orgName) {
            let enrolledUsers = bc.users(org.name);
            for (let j=0; j<enrolledUsers.length; j++) {
                let user = enrolledUsers[j];
                if (user.enrollmentID === req.params.userName) {
                    logger.info(`GET    /api/:bid/wallet/:userName/:orgName bid: ${doc.id}  userName: ${user.enrollmentID}  orgName: ${org.name}    status: 200`);
                    res.download(path.join(__dirname, '..', '..', 'blockchain_base', 'chains', `bc_${doc.owner}`, 'wallets', `wallet_${org.id}/${user.enrollmentID}.id`));
                    return;
                }
            }
        }
    }
    logger.error(`GET    /api/:bid/wallet/:userName/:orgName bid: ${doc.id}  userName: None  orgName: ${req.params.orgName}  status: 400    error: User does not exists under given organization`);
    res.status(400).json({ message: 'User does not exists under given organization'})
});

router.get('/:bid/organizations', function(req, res) {
    let doc = res.locals.doc;
    let bc = new Blockchain(doc.orderers, doc.orgs, doc.owner, doc.channels, doc.status, doc.block, doc.benchmark);
    logger.info(`GET    /api/:bid/organizations bid: ${doc.id}  status: 200`);
    res.json(bc.info.orgs);
});

router.get('/:bid/users', authenticateSession, isAdmin, function(req, res) {
    let doc = res.locals.doc;
    let bc = new Blockchain(doc.orderers, doc.orgs, doc.owner, doc.channels, doc.status, doc.block, doc.benchmark);
    logger.info(`GET    /api/:bid/users user: ${req.session.user.username}   bid: ${doc.id}  status: 200`);
    res.json(bc.users());
});

router.get('/:bid/users/:orgName', authenticateSession, isAdmin, function(req, res) {
    let doc = res.locals.doc;
    let bc = new Blockchain(doc.orderers, doc.orgs, doc.owner, doc.channels, doc.status, doc.block, doc.benchmark);
    logger.info(`GET    /api/:bid/users/:orgName    user: ${req.session.user.username}   bid: ${doc.id}  orgName: ${req.params.orgName}  status: 200`);
    res.json(bc.users(req.params.orgName));
});

router.post('/:bid/users', authenticateSession, isAdmin, async function(req, res) {
    let doc = res.locals.doc;
    let body = req.body;
    if (doc.status) {
        let bc = new Blockchain(doc.orderers, doc.orgs, doc.owner, doc.channels, doc.status, doc.block, doc.benchmark);
        let index = translateUserOrg(doc, body);
        if (index > -1) {
            try {
                body.org = doc.orgs[index].id;
                let client = { enrollmentID: body.name, org: body.org, department: body.department, type: "client" };
                await bc.enroll(client);
                appendNewChainUser(client, doc.id);
                logger.info(`POST   /api/:bid/users user: ${req.session.user.username}   bid: ${doc.id}  status: 201`);
                res.status(201).json({});
            } catch (err) {
                logger.error(`POST   /api/:bid/users user: ${req.session.user.username}   bid: ${doc.id}  status: 400    error: ${err.message}`);
                res.status(400).json({ message: err.message });
            }
        } else {
            logger.error(`POST   /api/:bid/users user: ${req.session.user.username}   bid: ${doc.id}  status: 400    error: Username does not belong to a registered organization`);
            res.status(400).json({ message: 'Username does not belong to a registered organization' });
        }
    } else {
        logger.error(`POST   /api/:bid/users user: ${req.session.user.username}   bid: ${doc.id}  status: 400    error: Resource not initialized`);
        res.status(400).json({ message: 'Resource not initialized' });   
    }
});

router.get('/:bid/contracts', function(req, res) {
    let doc = res.locals.doc;
    let bc = new Blockchain(doc.orderers, doc.orgs, doc.owner, doc.channels, doc.status, doc.block, doc.benchmark);
    logger.info(`GET    /api/:bid/contracts bid: ${doc.id}  status: 200`);
    res.json(bc.contracts);
});

router.post('/:bid/contracts', addParams, upload.array('files', 2), async function(req, res) {
    let doc = res.locals.doc;
    let body = req.body;
    if (doc.status) {
        let bc = new Blockchain(doc.orderers, doc.orgs, doc.owner, doc.channels, doc.status, doc.block, doc.benchmark);
        try {
            let cid = await bc.installContract(body.channel, body.name, body.version);
            body.id = cid;
            appendNewChainContract(body, doc.id);
            logger.info(`POST   /api/:bid/contracts bid: ${doc.id}  status: 201`);
            res.status(201).json({ cid: cid.cid });
        } catch (err) {
            logger.error(`POST   /api/:bid/contracts bid: ${doc.id}  status: 400 error: ${err.message}`);
            res.status(400).json({ message: err.message });
        }
    } else {
        logger.error(`POST   /api/:bid/contracts bid: ${doc.id}  status: 400    error: Resource not initialized`);
        res.status(400).json({ message: 'Resource not initialized' });  
    } 
});

/*router.get('/:bid/contracts/:cid', function(req, res) {
    let doc = res.locals.doc;
    let bc = new Blockchain(doc.orderers, doc.orgs, doc.owner, doc.channels, doc.status, doc.block, doc.benchmark);
    res.json(bc.contract(req.params.cid))
});*/

/*router.delete('/:bid/contracts/:cid', async function(req, res) {
    let doc = res.locals.doc;
    let bc = new Blockchain(doc);
    let contract = bc.contracts(req.params.cid);
    await bc.removeContract(contract);
    removeChainContract(contract);
});*/

// remove async
/*router.post('/:bid/:cid/document/insert', upload.single('document'), prepareEndpoint, function(req, res) {
    let doc = res.locals.doc;
    let bc = new Blockchain(doc.orderers, doc.orgs, doc.owner, doc.channels, doc.status, doc.block, doc.benchmark);
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
    let bc = new Blockchain(doc.orderers, doc.orgs, doc.owner, doc.channels, doc.status, doc.block, doc.benchmark);
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
});*/

router.post('/:bid/:cid/insert', prepareEndpoint, async function(req, res) {
    let doc = res.locals.doc;
    let bc = new Blockchain(doc.orderers, doc.orgs, doc.owner, doc.channels, doc.status, doc.block, doc.benchmark);
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
            inTransit: Date.now() - startTime
        });
        newTX.save();
        logger.info(`POST   /api/:bid/:cid/insert   client: ${req.body.requestor}   bid: ${doc.id}  cid: ${req.params.cid}  status: 201`);
        res.status(201).json(result);
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
        logger.error(`POST   /api/:bid/:cid/insert   client: ${req.body.requestor}   bid: ${doc.id}  cid: ${req.params.cid}  status: 500    error: ${err.message}`);
        res.status(500).json({ error: err.message });
    }
});

router.post('/:bid/:cid/evaluate', prepareEndpoint, async function(req, res) {
    let doc = res.locals.doc;
    let bc = new Blockchain(doc.orderers, doc.orgs, doc.owner, doc.channels, doc.status, doc.block, doc.benchmark);
    let endpoint = res.locals.endpoint;
    let message = {
        method: req.body.message.method,
        args: req.body.message.args,
        data: {}
    };
    let startTime = Date.now();
    try {
        let result = await bc.evaluate(message, endpoint, true);
        let newTX = new Transaction({
            bid: req.params.bid,
            cid: req.params.cid,
            endpoint: message.method,
            exceptionRaised: false,
            type: 'query',
            inTransit: Date.now() - startTime
        });
        newTX.save();
        logger.info(`POST   /api/:bid/:cid/evaluate client: ${req.body.requestor}   bid: ${doc.id}  cid: ${req.params.cid}  status: 200`);
        res.json(result);
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
        logger.error(`POST   /api/:bid/:cid/evaluate client: ${req.body.requestor}   bid: ${doc.id}  cid: ${req.params.cid}  status: 500    error: ${err.message}`);
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