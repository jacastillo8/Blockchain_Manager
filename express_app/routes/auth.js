// auth.js

const express = require('express');
const bcrypt = require('bcryptjs');
const User = require('../models/user'); // Import the User model
require('dotenv').config();  // Load environment variables

const router = express.Router();

// Middleware to check if the user is authenticated
const authenticateSession = (req, res, next) => {
  if (req.session.user) {
    next();
  } else {
    return res.status(401).json({ message: 'Access Denied: Please log in to access this resource.' });
  }
};

// Middleware to check if the user is an admin
const isAdmin = (req, res, next) => {
  if (req.session.user && req.session.user.role === 'admin') {
    next();
  } else {
    return res.status(403).json({ message: 'Access Denied: Admins Only' });
  }
};

// Admin Creation Route (only accessible with a setup key)
router.post('/create-admin', async (req, res) => {
    const { email, password } = req.body;
    const setupKey = req.header('Setup-Key'); // Setup key provided in the headers
    const storedSetupKey = process.env.SETUP_KEY; // The setup key stored in the .env file
  
    // Check if the provided setup key matches the stored setup key
    if (setupKey !== storedSetupKey) {
      return res.status(403).json({ message: 'Access Denied: Invalid Setup Key' });
    }
  
    try {
      // Check if the admin username already exists
      const userExists = await User.findOne({ username: email });
      if (userExists) {
        return res.status(400).json({ message: 'Admin account with this username already exists.' });
      }
  
      // Hash the password before storing it
      const salt = await bcrypt.genSalt(10);
      const passwordHash = await bcrypt.hash(password, salt);
  
      // Create and store the new admin in MongoDB
      const newAdmin = new User({ username: email, passwordHash, role: 'admin' });
      await newAdmin.save();
  
      res.status(201).json({});
    } catch (err) {
      res.status(500).json({ message: err.message });
    }
  });

// Signup Route
router.post('/register', async (req, res) => {
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
});

// Login Route using Sessions
router.post('/login', async (req, res) => {
  const { email, password } = req.body;

  try {
    // Find the user by username
    const user = await User.findOne({ username: email });
    if (!user) {
      return res.status(400).json({ message: 'Invalid username or password' });
    }

    // Check if the password is correct
    const validPassword = await bcrypt.compare(password, user.passwordHash);
    if (!validPassword) {
      return res.status(400).json({ message: 'Invalid username or password' });
    }

    // Set the user information in the session
    req.session.user = { username: user.username, role: user.role };

    res.status(200).json({});
  } catch (err) {
    res.status(500).json({ message: err.message });
  }
});

// Logout Route (destroy session)
router.get('/logout', (req, res) => {
  req.session.destroy(err => {
    if (err) {
      return res.status(500).json({ message: 'Error logging out' });
    }
    res.clearCookie('connect.sid'); // Clear the session cookie
    return res.status(200).redirect('/');
  });
});

// Protected Route Example (for any authenticated user)
/*router.get('/protected', authenticateSession, (req, res) => {
  res.json({ message: `Welcome ${req.session.user.username}, you have successfully accessed a protected resource!` });
});

// Admin-Only Route
router.get('/admin', authenticateSession, isAdmin, (req, res) => {
  res.json({ message: `Welcome Admin ${req.session.user.username}, this is sensitive admin data.` });
});*/

module.exports = router;
module.exports.authenticateSession = authenticateSession;
module.exports.isAdmin = isAdmin;