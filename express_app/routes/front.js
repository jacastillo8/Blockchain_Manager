const express = require('express');
const router = express.Router();

const { authenticateSession, isAdmin } = require('./auth');

router.get('/', function(req, res) {
    res.render('home');
});

router.get('/blockchain', function(req, res) {
    res.render('chain', { bid: req.query.bid });
});

router.get('/channel', function(req, res) {
    res.render('channel', { bid: req.query.bid });
});

router.get('/organizations', function(req, res) {
    res.render('orgs', { bid: req.query.bid });
});

router.get('/block', function(req, res) {
    res.render('block', { bid: req.query.bid });
});

router.get('/contracts', function(req, res) {
    res.render('contracts', { bid: req.query.bid, chid: req.query.chid });
});

router.get('/newcontract', function(req, res) {
    res.render('newcontract', { bid: req.query.bid, chid: req.query.chid });
});

router.get('/users', function(req, res) {
    res.render('users', { bid: req.query.bid, oname: req.query.oname });
});

router.get('/newuser', function(req, res) {
    res.render('newuser', { bid: req.query.bid, oname: req.query.oname });
});

router.get('/new', authenticateSession, isAdmin, function(req, res) {
    res.render('newchain');
});

router.get('/login', function(req, res) {
    res.render('login');
});

router.get('/register', function(req, res) {
    res.render('register');
});

module.exports = router;