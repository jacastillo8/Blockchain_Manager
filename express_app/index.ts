require('dotenv').config();
const express = require('express');
const path = require('path');
const mongoose = require('mongoose');

// Deprecation Warnings removed
mongoose.set('useNewUrlParser', true);
mongoose.set('useFindAndModify', false);
mongoose.set('useCreateIndex', true);
mongoose.set('useUnifiedTopology', true);

mongoose.connect('mongodb://localhost:27017/Blockchain');
let db = mongoose.connection;

// Check DB connection
db.once('open', function(){
    console.log('Connected to MongoDB');
});

// Check for DB errors
db.on('error', function(err: any){
    console.log(err);
});

db.on('disconnected', function() {
    console.log('MongoDB Disconnected');
})

const app = express();
app.use(express.urlencoded({ extended: true }));
app.use(express.json({ limit: "50mb" }));

// Setting EJS engine
app.set('views', path.join(__dirname, 'views'));
app.set('view engine', 'ejs');

app.use(function (req: any, res: any, next: any) {
    //Enabling CORS
    res.header("Access-Control-Allow-Origin", "*");
    res.header("Access-Control-Allow-Methods", "GET,HEAD,OPTIONS,POST,PUT");
    res.header("Access-Control-Allow-Headers", "Origin, X-Requested-With, Content-Type, Accept, x-client-key, x-client-token, x-client-secret, Authorization");
    next();
});

app.get('/', function(req: any, res: any) {
    res.send({ msg: "Server Online" });
});

const api = require('./routes/api');
const metrics = require('./routes/metrics');
app.use('/api', api);
app.use('/metrics', metrics);

let port = process.env.PORT;
app.listen(port, function() {
    console.log(`Serving on port ${port}...`);
});