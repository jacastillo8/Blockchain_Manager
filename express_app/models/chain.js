let mongoose = require('mongoose');

let chainSchema = mongoose.Schema({
    owner: {
        type: String,
        required: true
    },
    orderers: {
        type: String,
        required: true
    },
    consensus: {
        type: String,
        required: true
    },
    channels: [Object],
    orgs: [Object],
    block: Object,
    status: {
        type: Boolean,
        required: true
    },
    init_benchmark: {
        type: Boolean,
        required: true
    },
    id: {
        type: String,
        required: true
    }
}, { collection: 'Chains' });

let Chain = module.exports = mongoose.model('Chain', chainSchema);