const winston = require('winston');

const logger = winston.createLogger({
  level: 'info', // Logs 'info' and all levels above it (warn, error)
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.printf(({ timestamp, level, message }) => {
      return `[${timestamp}] ${level.toUpperCase()}: ${message}`;
    })
  ),
  transports: [
    // Everything logs to this file
    new winston.transports.File({ filename: './server.log' }),

    // Show logs in console too
    new winston.transports.Console()
  ]
});

module.exports = logger;
