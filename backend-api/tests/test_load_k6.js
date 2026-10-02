import http from 'k6/http';
import { check, group, sleep } from 'k6';
import { Rate, Trend, Counter, Gauge } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('errors');
const duration = new Trend('duration');
const throughput = new Counter('throughput');
const activeUsers = new Gauge('active_users');

export const options = {
  // Scenario 1: Ramp-up (linear increase in VUs)
  stages: [
    { duration: '2m', target: 10 },    // Ramp up to 10 users
    { duration: '5m', target: 50 },    // Ramp up to 50 users
    { duration: '5m', target: 50 },    // Stay at 50 users
    { duration: '2m', target: 0 },     // Ramp down to 0 users
  ],
  thresholds: {
    // Error rate must be < 5%
    'errors': ['rate<0.05'],
    // 95% of requests must be < 2s
    'duration': ['p(95)<2000'],
    // HTTP errors must be < 1%
    'http_req_failed': ['rate<0.01'],
  },
};

const API_BASE = __ENV.API_URL || 'http://localhost:8001';
const AUTH_TOKEN = __ENV.AUTH_TOKEN || 'test-token';

export default function () {
  // Track active users
  activeUsers.add(1);

  group('API Catalog Operations', () => {
    // GET catalog list
    let response = http.get(`${API_BASE}/api/v2/catalog`, {
      headers: {
        'Authorization': `Bearer ${AUTH_TOKEN}`,
        'X-API-Version': '2.0',
      },
    });

    check(response, {
      'catalog list status 200': (r) => r.status === 200,
      'catalog response time < 1s': (r) => r.timings.duration < 1000,
    });

    duration.add(response.timings.duration);
    throughput.add(1);
    if (response.status !== 200) {
      errorRate.add(1);
    }

    sleep(1);
  });

  group('API Order Operations', () => {
    // GET orders list
    let response = http.get(`${API_BASE}/admin/orders`, {
      headers: {
        'Authorization': `Bearer ${AUTH_TOKEN}`,
      },
    });

    check(response, {
      'orders list status 200': (r) => r.status === 200,
      'orders response time < 2s': (r) => r.timings.duration < 2000,
    });

    duration.add(response.timings.duration);
    throughput.add(1);
    if (response.status !== 200) {
      errorRate.add(1);
    }

    sleep(1);
  });

  group('Order Creation Load', () => {
    // POST create order
    const payload = JSON.stringify({
      customer_name: `Customer ${__VU}-${__ITER}`,
      customer_email: `customer-${__VU}-${__ITER}@loadtest.com`,
      customer_phone: '+351 91 1234567',
      lines: [
        {
          ean: '5901234123457',
          quantity: Math.floor(Math.random() * 5) + 1,
          price: 25.50,
        },
      ],
    });

    let response = http.post(`${API_BASE}/admin/orders`, payload, {
      headers: {
        'Authorization': `Bearer ${AUTH_TOKEN}`,
        'Content-Type': 'application/json',
      },
    });

    check(response, {
      'order creation status 201': (r) => r.status === 201,
      'order creation response time < 3s': (r) => r.timings.duration < 3000,
    });

    duration.add(response.timings.duration);
    throughput.add(1);
    if (response.status !== 201) {
      errorRate.add(1);
    }

    sleep(1);
  });

  group('Inventory Lookup', () => {
    // GET inventory for specific EAN
    let response = http.get(`${API_BASE}/api/v2/inventory/5901234123457`, {
      headers: {
        'Authorization': `Bearer ${AUTH_TOKEN}`,
      },
    });

    check(response, {
      'inventory lookup status 200/404': (r) => [200, 404].includes(r.status),
      'inventory response time < 500ms': (r) => r.timings.duration < 500,
    });

    duration.add(response.timings.duration);
    throughput.add(1);
    if (![200, 404].includes(response.status)) {
      errorRate.add(1);
    }

    sleep(1);
  });

  group('Rate Limiting Stress Test', () => {
    // Simulate rapid-fire requests
    for (let i = 0; i < 20; i++) {
      let response = http.get(`${API_BASE}/api/v2/catalog`, {
        headers: {
          'Authorization': `Bearer ${AUTH_TOKEN}`,
        },
      });

      // 429 (rate limited) is OK for this test
      check(response, {
        'status is 200 or 429': (r) => [200, 429].includes(r.status),
      });

      if (response.status === 429) {
        errorRate.add(0.1);  // Partial error
      } else {
        duration.add(response.timings.duration);
        throughput.add(1);
      }
    }

    sleep(2);  // Cool down
  });

  // Decrease active users gauge
  activeUsers.add(-1);
}

export function handleSummary(data) {
  // Custom summary output
  console.log('===== Load Test Summary =====');
  console.log(`Total Requests: ${data.metrics.throughput.values.count}`);
  console.log(`Error Rate: ${(data.metrics.errors.values.rate * 100).toFixed(2)}%`);
  console.log(`P95 Duration: ${data.metrics.duration.values['p(95)']}ms`);
  console.log(`P99 Duration: ${data.metrics.duration.values['p(99)']}ms`);

  return {
    'summary.json': JSON.stringify(data),
    stdout: textSummary(data, { indent: ' ', enableColors: true }),
  };
}

function textSummary(data, options) {
  let summary = '\n===== k6 Test Summary =====\n';
  summary += `Total Duration: ${(data.state.testRunDurationMs / 1000).toFixed(1)}s\n`;
  summary += `Total Requests: ${data.metrics.http_requests.values.count}\n`;
  summary += `Failed Requests: ${data.metrics.http_req_failed.values.count}\n`;
  summary += `Error Rate: ${(data.metrics.http_req_failed.values.rate * 100).toFixed(2)}%\n`;
  summary += `Throughput: ${(data.metrics.http_requests.values.count / (data.state.testRunDurationMs / 1000)).toFixed(2)} req/s\n`;
  return summary;
}
