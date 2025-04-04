require('dotenv').config();
const express = require('express');
const session = require('express-session');
//const cookieParser = require('cookie-parser');
const path = require('path');
const mongoose = require('mongoose');
const cons = require('consolidate');

const logger = require('./services/utils/logger');

// Deprecation Warnings removed
mongoose.set('useNewUrlParser', true);
mongoose.set('useFindAndModify', false);
mongoose.set('useCreateIndex', true);
mongoose.set('useUnifiedTopology', true);

mongoose.connect('mongodb://localhost:27017/Blockchain');
let db = mongoose.connection;

// Check DB connection
db.once('open', function(){
    logger.info("BCM connected to DB");
});

// Check for DB errors
db.on('error', function(err: any){
    logger.error(err);
});

db.on('disconnected', function() {
    logger.error('BCM disconnected from DB');
})

const app = express();
app.use(express.urlencoded({ extended: true }));
//app.use(cookieParser());
app.use(express.json({ limit: "50mb" }));

// Setting EJS engine
app.set('views', path.join(__dirname, 'views'));
app.use(express.static(path.join(__dirname, 'public')));
app.set('view engine', 'ejs');

// Session middleware configuration
app.use(session({
    secret: process.env.SECRET_KEY, // Store session secret in .env
    resave: false,                      // Don't save session if unmodified
    saveUninitialized: true,            // Save new sessions
    cookie: { secure: false }           // In production, set secure: true if using https
}));

// Middleware to make user available to all views
app.use((req: any, res: any, next: any) => {
    res.locals.user = req.session.user; // Makes the logged-in user available in views
    next();
});

app.use(function (req: any, res: any, next: any) {
    //Enabling CORS
    res.header("Access-Control-Allow-Origin", "*");
    res.header("Access-Control-Allow-Methods", "GET,HEAD,OPTIONS,POST,PUT");
    res.header("Access-Control-Allow-Headers", "Origin, X-Requested-With, Content-Type, Accept, x-client-key, x-client-token, x-client-secret, Authorization");
    next();
});

const api = require('./routes/api');
const front = require('./routes/front');
const metrics = require('./routes/metrics');
const auth = require('./routes/auth');
app.use('/api', api);
app.use('/', front);
app.use('/metrics', metrics);
app.use('/auth', auth);

let port = process.env.PORT;
app.listen(port, function() {
    logger.info(`BCM is serving on port ${port}`);
});