/**
 * Load testing for payment saga distributed transaction
 *
 * Tests saga pattern reliability under load:
 * - Order creation triggers saga
 * - Payment processing in parallel
 * - Inventory deduction
 * - Email notifications
 * - Compensation on failure
 *
 * Run with: k6 run payment-saga.js
 */

import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';

// Metrics
const sagaDuration = new Trend('saga_duration');
const paymentSuccess = new Rate('payment_success');
const sagaCompensation = new Counter('saga_compensation');
const errors = new Counter('errors');

export const options = {
  stages: [
    { duration: '1m', target: 20 },
    { duration: '3m', target: 50 },
    { duration: '2m', target: 100 },
    { duration: '2m', target: 50 },
    { duration: '1m', target: 0 },
  ],
  thresholds: {
    'saga_duration': ['p(95)<2000', 'p(99)<5000'],
    'payment_success': ['rate>0.99'],
    'http_req_failed': ['rate<0.05'],
  },
};

function createOrderWithPayment(customerId, amount) {
  const startTime = Date.now();

  const orderPayload = JSON.stringify({
    customer_id: customerId,
    items: [
      {
        sku: `product-${Math.floor(Math.random() * 100)}`,
        quantity: Math.floor(Math.random() * 5) + 1,
        unit_price: amount,
      },
    ],
    total_amount: amount,
  });

  const orderRes = http.post(`${BASE_URL}/api/orders`, orderPayload, {
    headers: { 'Content-Type': 'application/json' },
  });

  if (orderRes.status !== 201) {
    errors.add(1);
    return null;
  }

  const orderId = orderRes.json('id');

  // Process payment
  const paymentPayload = JSON.stringify({
    order_id: orderId,
    amount: amount,
    payment_method: 'credit_card',
    card_token: 'tok_test_' + Math.random().toString(36).substr(2, 9),
  });

  const paymentRes = http.post(`${BASE_URL}/api/payments`, paymentPayload, {
    headers: { 'Content-Type': 'application/json' },
  });

  const duration = Date.now() - startTime;
  sagaDuration.add(duration);

  const success = paymentRes.status === 200 || paymentRes.status === 201;
  paymentSuccess.add(success);

  if (!success) {
    errors.add(1);

    // Check if compensation was triggered
    const compensationRes = http.get(`${BASE_URL}/api/orders/${orderId}/status`);
    if (compensationRes.json('compensation_triggered') === true) {
      sagaCompensation.add(1);
    }
  }

  return {
    orderId,
    success,
    duration,
    status: paymentRes.status,
  };
}

function checkOrderStatus(orderId) {
  const res = http.get(`${BASE_URL}/api/orders/${orderId}`);

  return {
    status: res.status,
    orderStatus: res.json('status'),
    paymentStatus: res.json('payment.status'),
  };
}

function listOrders(customerId) {
  const res = http.get(
    `${BASE_URL}/api/customers/${customerId}/orders?limit=10`
  );

  return {
    status: res.status,
    count: res.json('length'),
  };
}

export default function () {
  const customerId = `customer-${__VU}`;

  group('Create Order with Payment Saga', () => {
    const orderResult = createOrderWithPayment(customerId, 199.99);

    if (orderResult) {
      check(orderResult, {
        'payment completed': (r) => r.status === 200 || r.status === 201,
        'saga duration < 2s': (r) => r.duration < 2000,
      });

      sleep(1);

      group('Verify Order Status', () => {
        const statusRes = checkOrderStatus(orderResult.orderId);

        check(statusRes, {
          'status endpoint accessible': (r) => r.status === 200,
          'order status set': (r) => r.orderStatus !== null,
          'payment status recorded': (r) => r.paymentStatus !== null,
        });
      });
    }
  });

  group('List Customer Orders', () => {
    const listRes = listOrders(customerId);

    check(listRes, {
      'list status 200': (r) => r.status === 200,
      'orders returned': (r) => r.count >= 0,
    });
  });

  sleep(Math.random() * 3 + 1);
}

export function teardown() {
  console.log(`Total saga compensations: ${sagaCompensation.value}`);
  console.log(`Total errors: ${errors.value}`);
}
