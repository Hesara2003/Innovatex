#!/usr/bin/env node
/**
 * Minimal Node.js client for the Project Sentinel event stream.
 *
 * Usage:
 *   node client_example_node.js --host 127.0.0.1 --port 8765 --limit 5
 *
 * Specify --limit 0 (default) to keep reading indefinitely.
 */

const net = require('net');

function parseArgs(argv) {
  const args = { host: '127.0.0.1', port: 8765, limit: 0 };
  for (let i = 2; i < argv.length; i++) {
    const key = argv[i];
    if (key === '--host' && argv[i + 1]) {
      args.host = argv[++i];
    } else if (key === '--port' && argv[i + 1]) {
      args.port = parseInt(argv[++i], 10);
    } else if (key === '--limit' && argv[i + 1]) {
      args.limit = parseInt(argv[++i], 10);
    }
  }
  return args;
}

function formatBanner(frame) {
  const datasets = Array.isArray(frame.datasets) ? frame.datasets.join(', ') : 'unknown';
  const events = typeof frame.events === 'number' ? frame.events : 'unknown';
  const loop = typeof frame.loop === 'boolean' ? frame.loop : 'unknown';
  const speed = typeof frame.speed_factor === 'number' ? frame.speed_factor : 'unknown';
  const cycle = frame.cycle_seconds ?? 'unknown';
  console.log('--- Stream Banner ---');
  console.log(`Service: ${frame.service}`);
  console.log(`Datasets: ${datasets}`);
  console.log(`Events: ${events}`);
  console.log(`Looping: ${loop}`);
  console.log(`Speed factor: ${speed}`);
  console.log(`Cycle seconds: ${cycle}`);
  console.log('---------------------');
}

function printEvent(eventCount, frame) {
  const dataset = frame.dataset ?? 'unknown';
  const sequence = frame.sequence ?? '?';
  const ts = frame.timestamp ?? 'unknown';
  const original = frame.original_timestamp ?? 'n/a';
  console.log(`[${eventCount}] dataset=${dataset} sequence=${sequence}`);
  console.log(` timestamp: ${ts}`);
  console.log(` original : ${original}`);
  if (frame.event) {
    console.dir(frame.event, { depth: null });
  }
  console.log('-');
}

function main() {
  const options = parseArgs(process.argv);
  let buffer = '';
  let eventCount = 0;

  const socket = net.createConnection({ host: options.host, port: options.port }, () => {
    console.log(`Connected to ${options.host}:${options.port}`);
  });

  socket.setEncoding('utf8');

  socket.on('data', (chunk) => {
    buffer += chunk;
    let newlineIndex;
    while ((newlineIndex = buffer.indexOf('\n')) >= 0) {
      const line = buffer.slice(0, newlineIndex).trim();
      buffer = buffer.slice(newlineIndex + 1);
      if (!line) continue;
      try {
        const frame = JSON.parse(line);
        if (frame && typeof frame === 'object' && frame.service) {
          formatBanner(frame);
          continue;
        }
        eventCount += 1;
        printEvent(eventCount, frame);
        if (options.limit > 0 && eventCount >= options.limit) {
          console.log('Reached limit; closing connection.');
          socket.end();
          socket.destroy();
          return;
        }
      } catch (err) {
        console.error('Failed to parse frame:', err);
      }
    }
  });

  socket.on('error', (err) => {
    console.error('Socket error:', err.message);
    process.exitCode = 1;
  });

  socket.on('end', () => {
    console.log('Disconnected from server.');
  });
}

main();
