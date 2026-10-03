/**
 * k6 load testing scenarios for Diomika API
 * Run with: k6 run load_tests/k6_scenarios.js
 */

import http from "k6/http";
import { check, group, sleep } from "k6";
import { Rate, Trend, Counter, Gauge } from "k6/metrics";

// Custom metrics
const apiLatency = new Trend("api_latency");
const apiErrors = new Counter("api_errors");
const apiSuccess = new Counter("api_success");
const activeConnections = new Gauge("active_connections");

// Configuration
const BASE_URL = __ENV.BASE_URL || "http://localhost:8001";
const API_KEY = __ENV.API_KEY || "test-key";

// Test stages configuration
export const options = {
  stages: [
    { duration: "30s", target: 20 }, // Ramp up to 20 users
    { duration: "1m30s", target: 50 }, // Ramp up to 50 users
    { duration: "2m", target: 50 }, // Stay at 50 users
    { duration: "30s", target: 0 }, // Ramp down to 0 users
  ],
  thresholds: {
    "http_req_duration": ["p(99)<500", "p(95)<300", "p(50)<100"], // 99% under 500ms
    "http_req_failed": ["rate<0.1"], // Error rate < 10%
  },
  ext: {
    loadimpact: {
      projectID: 3400076,
      name: "Diomika API Load Test",
    },
  },
};

// Test data
const endpoints = [
  "/catalog",
  "/catalog/categories",
  "/catalog/search",
  "/health",
];

const postEndpoints = [
  {
    path: "/contact",
    body: JSON.stringify({
      name: "Test User",
      email: "test@example.com",
      subject: "Inquiry",
      message: "Test message",
    }),
  },
];

// Scenario: Ramp up and down
export function testRampUpDown() {
  group("Catalog endpoints", function () {
    endpoints.forEach((endpoint) => {
      const res = http.get(`${BASE_URL}${endpoint}`, {
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": API_KEY,
        },
      });

      const success = check(res, {
        "status is 200": (r) => r.status === 200,
        "response time < 500ms": (r) => r.timings.duration < 500,
        "has content": (r) => r.body.length > 0,
      });

      if (success) {
        apiSuccess.add(1);
      } else {
        apiErrors.add(1);
      }

      apiLatency.add(res.timings.duration);
      activeConnections.add(1);

      sleep(1);
    });
  });
}

// Scenario: Stress test
export function testStress() {
  group("Stress test", function () {
    const res = http.get(`${BASE_URL}/catalog`, {
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": API_KEY,
      },
    });

    check(res, {
      "status is 200": (r) => r.status === 200,
    });

    apiLatency.add(res.timings.duration);
  });
}

// Scenario: POST operations
export function testPostOperations() {
  group("POST operations", function () {
    postEndpoints.forEach((endpoint) => {
      const res = http.post(`${BASE_URL}${endpoint.path}`, endpoint.body, {
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": API_KEY,
        },
      });

      check(res, {
        "status is 200 or 201": (r) => r.status === 200 || r.status === 201,
        "response time < 1000ms": (r) => r.timings.duration < 1000,
      });

      apiLatency.add(res.timings.duration);
    });
  });
}

// Scenario: Rate limiting test
export function testRateLimiting() {
  group("Rate limiting", function () {
    for (let i = 0; i < 100; i++) {
      const res = http.get(`${BASE_URL}/catalog`, {
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": API_KEY,
        },
      });

      check(res, {
        "not rate limited": (r) => r.status !== 429,
      });

      if (res.status === 429) {
        apiErrors.add(1);
      }

      apiLatency.add(res.timings.duration);
    }
  });
}

// Scenario: Mixed operations
export function testMixedOperations() {
  group("Mixed operations", function () {
    // GET request
    const getRes = http.get(`${BASE_URL}/catalog`, {
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": API_KEY,
      },
    });

    check(getRes, {
      "GET successful": (r) => r.status === 200,
    });

    // POST request
    const postRes = http.post(
      `${BASE_URL}/contact`,
      JSON.stringify({
        name: "Load Test",
        email: "load@test.com",
        subject: "Test",
        message: "Load testing",
      }),
      {
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": API_KEY,
        },
      }
    );

    check(postRes, {
      "POST successful": (r) => r.status === 200 || r.status === 201,
    });

    sleep(1);
  });
}

// Scenario: Sustained load
export function testSustainedLoad() {
  group("Sustained load", function () {
    http.batch([
      {
        method: "GET",
        url: `${BASE_URL}/catalog`,
      },
      {
        method: "GET",
        url: `${BASE_URL}/catalog/categories`,
      },
      {
        method: "GET",
        url: `${BASE_URL}/health`,
      },
    ]);

    sleep(2);
  });
}

// Default export
export default function () {
  testRampUpDown();
}
