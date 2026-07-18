-- Write your migration SQL here
--
-- Example:
--   CREATE TABLE IF NOT EXISTS users (
--     id SERIAL PRIMARY KEY,
--     name TEXT NOT NULL,
--     created_at TIMESTAMP DEFAULT NOW()
--   );
CREATE TABLE ginse_operations (
  idempotency_key VARCHAR(200) PRIMARY KEY,
  request_fingerprint CHAR(64) NOT NULL,
  provider_operation_id VARCHAR(200) NOT NULL UNIQUE,
  status VARCHAR(20) NOT NULL CHECK (status IN ('succeeded')),
  output JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
