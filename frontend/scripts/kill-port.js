#!/usr/bin/env node
/* eslint-disable */

const { execSync } = require('child_process');

const port = process.argv[2] || process.env.PORT || 3000;

console.log(`Checking for processes running on port ${port}...`);

try {
  if (process.platform === 'win32') {
    const output = execSync(`netstat -ano | findstr :${port}`).toString();
    const lines = output.trim().split('\n');
    const pids = new Set();
    
    for (const line of lines) {
      const parts = line.trim().split(/\s+/);
      const pid = parts[parts.length - 1];
      if (pid && pid !== '0') {
        pids.add(pid);
      }
    }

    if (pids.size === 0) {
      console.log(`No active process found on port ${port}.`);
      process.exit(0);
    }

    for (const pid of pids) {
      try {
        execSync(`taskkill /F /PID ${pid}`);
        console.log(`✓ Terminated process PID ${pid} on port ${port}`);
      } catch {
        // ignore already terminated
      }
    }
  } else {
    // Linux / macOS
    try {
      const pids = execSync(`lsof -ti:${port}`).toString().trim();
      if (pids) {
        execSync(`kill -9 ${pids.split('\n').join(' ')}`);
        console.log(`✓ Terminated process(es) [${pids.split('\n').join(', ')}] on port ${port}`);
      } else {
        console.log(`No active process found on port ${port}.`);
      }
    } catch {
      // If lsof returned non-zero (e.g. no process listening), try fuser
      try {
        execSync(`fuser -k ${port}/tcp`, { stdio: 'ignore' });
        console.log(`✓ Cleared port ${port} using fuser.`);
      } catch {
        console.log(`No active process found listening on port ${port}.`);
      }
    }
  }
} catch (err) {
  console.log(`No active process found on port ${port}.`);
}
