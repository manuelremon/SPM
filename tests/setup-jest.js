// Mock fetch global
global.fetch = jest.fn();
global.TextEncoder = require('util').TextEncoder;
global.TextDecoder = require('util').TextDecoder;
