// auth.js
const express = require('express');
const bcrypt = require('bcryptjs');
const User = require('../models/user'); // Import the User model
require('dotenv').config();  // Load environment variables

const logger = require('../services/utils/logger');

const router = express.Router();

// Middleware to check if the user is authenticated
const authenticateSession = (req, res, next) => {
  if (req.session.user) {
    next();
  } else {
    logger.error(`function: authenticateSession user: ${req.session.user.username}  role: ${req.session.user.role}  status: 401 error: Access Denied. Authenticate to access this resource`);
    return res.status(401).json({ message: 'Please log in to access this resource' });
  }
};

// Middleware to check if the user is an admin
const isAdmin = (req, res, next) => {
  if (req.session.user && req.session.user.role === 'admin') {
    next();
  } else {
    logger.error(`function: isAdmin user: ${req.session.user.username}  role: ${req.session.user.role}  status: 403 error: Access Denied. Administrators only`);
    return res.status(403).json({ message: 'Administrators only' });
  }
};

// Admin Creation Route (only accessible with a setup key)
router.post('/createAdmin', async (req, res) => {
    const { email, password } = req.body;
    const setupKey = req.header('Setup-Key'); // Setup key provided in the headers
    const storedSetupKey = process.env.SETUP_KEY; // The setup key stored in the .env file
  
    // Check if the provided setup key matches the stored setup key
    if (setupKey !== storedSetupKey) {
      logger.error(`POST  /auth/createAdmin email: ${email} status: 403 error: Access Denied. Invalid setup key`);
      return res.status(403).json({ message: 'Invalid setup key' });
    }
  
    try {
      // Check if the admin username already exists
      const userExists = await User.findOne({ username: email });
      if (userExists) {
        logger.error(`POST  /auth/createAdmin email: ${email} status: 400 error: Admin account with this username already exists`);
        return res.status(400).json({ message: 'Admin account with this username already exists' });
      }
  
      // Hash the password before storing it
      const salt = await bcrypt.genSalt(10);
      const passwordHash = await bcrypt.hash(password, salt);
  
      // Create and store the new admin in MongoDB
      const newAdmin = new User({ username: email, passwordHash, role: 'admin' });
      await newAdmin.save();
      
      logger.info(`POST   /auth/createAdmin email: ${email} status: 201`);
      res.status(201).json({});
    } catch (err) {
      logger.error(`POST  /auth/createAdmin email: ${email} status: 500 error: ${err.message}`);
      res.status(500).json({ message: err.message });
    }
  });

// Signup Route
/*router.post('/register', async (req, res) => {
  const { email, password } = req.body;  // Role can be passed in request

  try {
    // Check if the username already exists
    const userExists = await User.findOne({ username: email });
    if (userExists) {
      return res.status(400).json({ message: 'User already exists' });
    }

    // Hash the password before storing it
    const salt = await bcrypt.genSalt(10);
    const passwordHash = await bcrypt.hash(password, salt);

    // Create and store the new user in MongoDB
    const newUser = new User({ username: email, passwordHash, role: 'student' });
    await newUser.save();

    res.status(201).json({});
  } catch (err) {
    res.status(500).json({ message: err.message });
  }
});*/

// Login Route using Sessions
router.post('/login', async (req, res) => {
  const { email, password } = req.body;

  try {
    // Find the user by username
    const user = await User.findOne({ username: email });
    if (!user) {
      logger.error(`POST  /auth/login user: ${email}  status: 400 error: Username does not exists`);
      return res.status(400).json({ message: 'Invalid username or password' });
    }

    // Check if the password is correct
    const validPassword = await bcrypt.compare(password, user.passwordHash);
    if (!validPassword) {
      logger.error(`POST  /auth/login user: ${email}  status: 400 error: Password (hash) does not match any records`);
      return res.status(400).json({ message: 'Invalid username or password' });
    }

    // Set the user information in the session
    req.session.user = { username: user.username, role: user.role };

    logger.info(`POST  /auth/login  user: ${email}  status: 200`);
    res.status(200).json({});
  } catch (err) {
    logger.error(`POST  /auth/login user: ${email}  status: 500 error: ${err.message}`);
    res.status(500).json({ message: err.message });
  }
});

// Logout Route (destroy session)
router.get('/logout', (req, res) => {
  req.session.destroy(err => {
    if (err) {
      logger.error(`GET   /auth/logout  user: ${req.session.user.username}  status: 500 error: ${err.message}`);
      return res.status(500).json({ message: 'Error logging out' });
    }
    res.clearCookie('connect.sid'); // Clear the session cookie
    logger.info(`GET   /auth/logout  user: ${req.session.user.username}  status: 200`);
    return res.status(200).redirect('/');
  });
});

module.exports = router;
module.exports.authenticateSession = authenticateSession;
module.exports.isAdmin = isAdmin;