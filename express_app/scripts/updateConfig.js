const fs = require('fs');
const path = require('path');

const configPath = path.join('node_modules', 'fabric-common', 'config', 'default.json');
const basePath = path.join(__dirname, '..', configPath);

let config = JSON.parse(fs.readFileSync(basePath).toString('utf-8'));
config['discovery-cache-life'] = 300000 // Original: 300000
config['request-timeout'] = 45000 // Original: 45000
config['connection-options']['request-timeout'] = 45000 // Original 45000
config['connection-options']['grpc.keepalive_timeout_ms'] = 20000 //Original: 20000
fs.writeFileSync(basePath, JSON.stringify(config, null, 2))
console.log(config)