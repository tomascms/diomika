/**
 * Load testing for order API using k6
 *
 * Run with: k6 run order-api.js
 * For staging: k6 run --env STAGE=staging order-api.js
 * For production: k6 run --env STAGE=production order-api.js
 */

import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { Rate, Trend, Counter, Gauge } from 'k6/metrics';

// Configuration
const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const STAGE = __ENV.STAGE || 'development';

// Custom metrics
const duration = new Trend('request_duration');
const orderCreateRate = new Rate('order_create_success');
const errors = new Counter('errors');
const vus = new Gauge('vus');

// Test options
export const options = {
  stages: [
    { duration: '30s', target: 10 },    // Ramp up
    { duration: '2m', target: 50 },     // Peak load
    { duration: '1m', target: 25 },     // Scale down
    { duration: '30s', target: 0 },     // Ramp down
  ],
  thresholds: {
    'http_req_duration': ['p(95)<500', 'p(99)<1000'],
    'http_req_failed': ['rate<0.1'],
    'order_create_success': ['rate>0.95'],
  },
};

// Generate unique customer email for each iteration
function generateCustomerEmail() {
  return `load-test-${Date.now()}-${Math.random().toString(36).substr(2, 9)}@example.com`;
}

// Create a test order
function createOrder(authToken, customerEmail) {
  const payload = JSON.stringify({
    customer_email: customerEmail,
    items: [
      {
        sku: 'test-product-1',
        quantity: 1,
        unit_price: 99.99,
        description: 'Test Product',
      },
    ],
    shipping_address: '123 Main St, Test City, 12345',
    total_amount: 99.99,
  });

  const headers = {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${authToken}`,
  };

  const res = http.post(`${BASE_URL}/api/orders`, payload, { headers });

  return {
    status: res.status,
    order_id: res.json('id'),
    duration: res.timings.duration,
  };
}

// Fetch order details
function getOrderDetails(orderId, authToken) {
  const headers = {
    'Authorization': `Bearer ${authToken}`,
  };

  const res = http.get(`${BASE_URL}/api/orders/${orderId}`, { headers });

  return {
    status: res.status,
    duration: res.timings.duration,
  };
}

// Browse products
function browseProducts() {
  const res = http.get(`${BASE_URL}/api/products?limit=20`);

  return {
    status: res.status,
    count: res.json('length'),
    duration: res.timings.duration,
  };
}

// Get product details
function getProductDetails(sku) {
  const res = http.get(`${BASE_URL}/api/products/${sku}`);

  return {
    status: res.status,
    duration: res.timings.duration,
  };
}

// Main test function
export default function () {
  vus.add(__VU);

  // Get auth token (in real scenario, this would be obtained from login)
  const authToken = 'test-token-' + __VU;

  group('Browse Catalog', () => {
    const res = browseProducts();
    duration.add(res.duration);

    check(res, {
      'browse products status 200': (r) => r.status === 200,
      'products returned': (r) => r.count > 0,
    }) || errors.add(1);

    sleep(1);
  });

  group('View Product Details', () => {
    const res = getProductDetails('test-product-1');
    duration.add(res.duration);

    check(res, {
      'product details status 200': (r) => r.status === 200,
    }) || errors.add(1);

    sleep(1);
  });

  group('Create Order', () => {
    const customerEmail = generateCustomerEmail();
    const res = createOrder(authToken, customerEmail);
    duration.add(res.duration);

    const success = check(res, {
      'order create status 201': (r) => r.status === 201,
      'order ID returned': (r) => r.order_id !== undefined && r.order_id !== null,
    });

    orderCreateRate.add(success);

    if (!success) {
      errors.add(1);
    }

    sleep(2);

    if (success && res.order_id) {
      group('Fetch Order Details', () => {
        const detailRes = getOrderDetails(res.order_id, authToken);
        duration.add(detailRes.duration);

        check(detailRes, {
          'order details status 200': (r) => r.status === 200,
        }) || errors.add(1);
      });
    }
  });

  sleep(2);
}

// Teardown function
export function teardown() {
  console.log('Load test completed');
  console.log(`Total errors: ${errors.value}`);
}
