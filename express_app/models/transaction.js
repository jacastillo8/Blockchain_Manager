let mongoose = require('mongoose');

let TransactionSchema = mongoose.Schema({
    bid: {
        type: String,
        required: true
    },
    cid: {
        type: String,
        required: true
    },
    endpoint: {
        type: String,
        required: true
    },
    exceptionRaised: {
        type: Boolean,
        required: true
    },
    inTransit: {
        type: Number,
        required: true
    },
    type: {
        type: String,
        required: true
    }
}, { collection: 'Transactions' });

let Transaction = module.exports = mongoose.model('Transaction', TransactionSchema);