const express = require('express');
const router = express.Router();
const logger = require('../services/utils/logger');

const { authenticateSession, isAdmin } = require('./auth');

router.get('/', function(req, res) {
    logger.info("GET    /   status: 200");
    res.render('home');
});

router.get('/blockchain', function(req, res) {
    logger.info(`GET    /blockchain bid: ${req.query.bid}    status: 200`);
    res.render('chain', { bid: req.query.bid });
});

router.get('/channel', function(req, res) {
    logger.info(`GET    /channel    bid: ${req.query.bid}   status: 200`);
    res.render('channel', { bid: req.query.bid });
});

router.get('/organizations', function(req, res) {
    logger.info(`GET    /organization   bid: ${req.query.bid}   status: 200`);
    res.render('orgs', { bid: req.query.bid });
});

router.get('/block', function(req, res) {
    logger.info(`GET    /block  bid: ${req.query.bid}   status: 200`);
    res.render('block', { bid: req.query.bid });
});

router.get('/contracts', function(req, res) {
    logger.info(`GET    /contracts  bid: ${req.query.bid}   chid: ${req.query.chid} status: 200`);
    res.render('contracts', { bid: req.query.bid, chid: req.query.chid });
});

router.get('/newcontract', function(req, res) {
    logger.info(`GET    /newcontract    bid: ${req.query.bid}    chid: ${req.query.chid} status: 200`);
    res.render('newcontract', { bid: req.query.bid, chid: req.query.chid });
});

router.get('/users', authenticateSession, isAdmin, function(req, res) {
    logger.info(`GET    /users  user: ${req.session.user.username}   bid: ${req.query.bid}   oname: ${req.query.oname}   status: 200`);
    res.render('users', { bid: req.query.bid, oname: req.query.oname });
});

router.get('/newuser', authenticateSession, isAdmin, function(req, res) {
    logger.info(`GET    /newuser    user: ${req.session.user.username}   bid: ${req.query.bid}   oname: ${req.query.oname}   status: 200`);
    res.render('newuser', { bid: req.query.bid, oname: req.query.oname });
});

router.get('/new', authenticateSession, isAdmin, function(req, res) {
    logger.info(`GET    /new    user: ${req.session.user.username}   status: 200`);
    res.render('newchain');
});

router.get('/login', function(req, res) {
    logger.info("GET    /login  status: 200")
    res.render('login');
});

/*router.get('/register', function(req, res) {
    res.render('register');
});*/

module.exports = router;