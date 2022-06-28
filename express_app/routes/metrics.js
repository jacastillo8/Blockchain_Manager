const express = require('express');
const stats = require('simple-statistics');

const { Blockchain } = require('../services/Blockchain');
const { storeChainId, updateChainId, appendNewChainUser, 
    generateChainId, searchChainId, appendNewChainContract } = require('../services/ChainModel');

const Transaction = require('../models/transaction');

const router = express.Router();

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

async function checkContractId(req, res, next) {
    let doc = res.locals.doc;
    let bc = new Blockchain(doc);
    let contract = bc.contract(req.params.cid);
    if (contract.length !== 0) {
        next();
        return
    } 
    res.status(404).json({ message: 'Contract not Found' });
    return
}

router.all('/:bid*', checkChainId);
router.all('/:bid/:cid*', checkContractId);

router.get('/:bid/:cid/:method', async function(req, res) {
    let bid = req.params.bid;
    let cid = req.params.cid;
    let method = req.params.method;

    let documents = await Transaction.find({ bid, cid, endpoint: method }, 'endpoint exceptionRaised inTransit').exec();
    
    let delays = [];
    let success = 0;
    let total = 0;
    for (let i=0; i < documents.length; i++) {
        total++;
        if (!documents[i].exceptionRaised) {
            success++;
            delays.push(documents[i].inTransit);
        }
    }
    let metrics = {
        sampleTotal: total,
        sampleSuccess: success,
        sampleFail: total - success,
        max: stats.max(delays),
        min: stats.min(delays),
        mean: stats.mean(delays),
        stDev: stats.standardDeviation(delays)
    }
    res.json({ metrics, data: documents });
    return
});

module.exports = router;